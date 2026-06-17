"""Annual Energy Production (AEP) calculation pipeline."""

import yaml
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class _NoAliasSafeDumper(yaml.SafeDumper):
    """Safe YAML dumper that keeps result files explicit and readable."""

    def ignore_aliases(self, data):
        return True


def calculate_aep(
    power_curve_path: Path, 
    wind_resource_path: Path,
    output_path: Optional[Path] = None,
    plot: bool = False,
    plot_output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Calculate Annual Energy Production from power curves and wind resource.
    
    This function computes AEP, capacity factor, and cluster contributions
    from pre-computed power curves and wind resource probability distributions.
    
    Args:
        power_curve_path: Path to power_curves.yml file.
        wind_resource_path: Path to wind_resource.yml file.
        output_path: Optional path to save AEP results YAML. If None, no file is saved.
        plot: If True, generate and display/save plots.
        plot_output_dir: Directory to save plots. If None, plots are shown but not saved.
        
    Returns:
        Dictionary containing AEP results, capacity factor, and cluster contributions.
    """
    # Load data
    with open(power_curve_path, 'r') as f:
        power_data = yaml.safe_load(f)
    
    with open(wind_resource_path, 'r') as f:
        wind_data = yaml.load(f, Loader=yaml.FullLoader)
    
    # Calculate AEP components
    aep_results = _compute_aep_from_data(power_data, wind_data)
    
    # Save results if requested
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(
                aep_results,
                f,
                Dumper=_NoAliasSafeDumper,
                default_flow_style=False,
                sort_keys=False,
            )
        print(f"AEP results saved to {output_path}")
    
    # Generate plots if requested
    if plot:
        _generate_aep_plots(aep_results, power_data, wind_data, plot_output_dir)
    
    return aep_results


def _compute_aep_from_data(power_data: Dict[str, Any], 
                            wind_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute AEP from power curve and wind resource data.
    
    Args:
        power_data: Power curve data dictionary.
        wind_data: Wind resource data dictionary.
        
    Returns:
        Dictionary with AEP results.
    """
    HOURS_PER_YEAR = 8760

    def _energy_fields(energy_wh: float) -> Dict[str, float]:
        """Convert Wh to MWh for AEP reporting."""
        return {
            'aep_mwh': float(energy_wh / 1e6),
        }

    def _get_direction_centers_deg(n_directions: int) -> np.ndarray:
        """Get wind direction bin centers in degrees from metadata or fallback."""
        direction_bins = wind_data.get('wind_direction_bins', {})
        centers = direction_bins.get('bin_centers_deg', direction_bins.get('bin_centers', []))
        if len(centers) == n_directions:
            return np.array(centers, dtype=float)

        direction_bin_width = (
            wind_data.get('metadata', {}).get('wind_direction_bin_width_deg')
            or wind_data.get('metadata', {}).get('wind_direction_bin_width', 360.0 / max(n_directions, 1))
        )
        return np.arange(n_directions, dtype=float) * float(direction_bin_width) + float(direction_bin_width) / 2.0

    def _electrical_power_values(curve: Dict[str, Any]) -> List[float]:
        """Return electrical average cycle power values from a power-curve record."""
        if 'wind_speed_data' in curve:
            return [
                float(item['performance']['electrical_power']['average_cycle_power'])
                for item in curve['wind_speed_data']
            ]
        if 'electrical_cycle_power_w' in curve:
            return [float(power) for power in curve['electrical_cycle_power_w']]
        if 'power_values_electrical_w' in curve:
            return [float(power) for power in curve['power_values_electrical_w']]
        raise KeyError(
            "Power curve does not contain electrical power values. Expected "
            "wind_speed_data[*].performance.electrical_power.average_cycle_power."
        )

    # Extract probability data from wind resource
    probability_matrix = np.array(wind_data['probability_matrix']['data'], dtype=float)

    # Handle both 2D (profiles x wind_speeds) and 3D (profiles x wind_speeds x wind_directions)
    has_directional_data = probability_matrix.ndim == 3
    if has_directional_data:
        probability_matrix_3d = probability_matrix
        probability_matrix_2d = np.sum(probability_matrix_3d, axis=2)
    else:
        probability_matrix_2d = probability_matrix
        probability_matrix_3d = probability_matrix[:, :, np.newaxis]

    if 'reference_wind_speeds' not in power_data or 'power_curves' not in power_data:
        raise ValueError(
            "Unsupported power curve format. Expected keys 'reference_wind_speeds' and 'power_curves'."
        )

    bin_centers = np.array(power_data['reference_wind_speeds'])
    power_curves = power_data['power_curves']
    for profile in power_curves:
        profile['cycle_power_w'] = _electrical_power_values(profile)
    
    # Get wind speed bins from wind resource for probability matching
    wind_speed_bins = wind_data['wind_speed_bins']
    wind_bin_centers = np.array(
        wind_speed_bins.get('bin_centers_m_s',
        wind_speed_bins.get('bin_centers', []))
    )

    if wind_bin_centers.size == 0:
        wind_bin_centers = bin_centers.copy()

    # Align all arrays on the same wind-speed axis length.
    wind_bin_count = min(
        len(wind_bin_centers),
        probability_matrix_2d.shape[1] if probability_matrix_2d.ndim >= 2 else len(wind_bin_centers),
    )
    wind_bin_centers = wind_bin_centers[:wind_bin_count]
    probability_matrix_2d = probability_matrix_2d[:, :wind_bin_count]
    probability_matrix_3d = probability_matrix_3d[:, :wind_bin_count, :]

    # Build interpolated power curves for each profile on wind-resource speed bins.
    n_power_profiles = len(power_curves)
    n_wind_profiles = probability_matrix_2d.shape[0] if probability_matrix_2d.ndim >= 2 else 0
    if n_power_profiles != n_wind_profiles:
        raise ValueError(
            "Profile count mismatch between power curves and wind resource: "
            f"power_curves={n_power_profiles}, wind_resource_profiles={n_wind_profiles}."
        )

    profile_ids: List[int] = []
    profile_powers_interp: List[np.ndarray] = []
    for i, curve in enumerate(power_curves):
        profile_id = curve.get('profile_id', i + 1)
        powers = np.array(curve['cycle_power_w'], dtype=float)
        if len(bin_centers) != len(wind_bin_centers):
            powers_interp = np.interp(wind_bin_centers, bin_centers, powers)
        else:
            powers_interp = powers[:wind_bin_count]

        profile_ids.append(int(profile_id))
        profile_powers_interp.append(np.array(powers_interp[:wind_bin_count], dtype=float))

    # Build probability tensors matching the power-profile definition.
    profile_prob_2d = probability_matrix_2d[:, :wind_bin_count] / 100.0
    profile_prob_3d = probability_matrix_3d[:, :wind_bin_count, :] / 100.0

    # Compute per-profile AEP contributions.
    profile_contributions: List[Dict[str, Any]] = []
    profile_aep_wh = np.zeros(n_power_profiles, dtype=float)
    profile_frequencies = np.sum(profile_prob_2d, axis=1)
    profile_rated_powers = np.array(
        [float(np.max(powers)) if powers.size > 0 else 0.0 for powers in profile_powers_interp],
        dtype=float,
    )
    profile_rated_wind_speeds = np.array(
        [
            float(wind_bin_centers[int(np.argmax(powers))])
            if powers.size > 0 and wind_bin_centers.size > 0
            else 0.0
            for powers in profile_powers_interp
        ],
        dtype=float,
    )

    for i, profile_id in enumerate(profile_ids):
        energy_wh = float(np.sum(profile_powers_interp[i] * profile_prob_2d[i]) * HOURS_PER_YEAR)
        profile_aep_wh[i] = energy_wh
        profile_contributions.append({
            'profile_id': profile_id,
            'frequency': float(profile_frequencies[i]),
            'rated_power_w': float(profile_rated_powers[i]),
            'rated_wind_speed_m_s': float(profile_rated_wind_speeds[i]),
            **_energy_fields(energy_wh),
        })

    total_aep_wh = float(np.sum(profile_aep_wh))

    # Compute per-direction breakdown (if no directional matrix, this is one synthetic bin).
    n_directions = profile_prob_3d.shape[2]
    direction_centers_deg = _get_direction_centers_deg(n_directions)
    direction_bin_width_deg = (
        wind_data.get('metadata', {}).get('wind_direction_bin_width_deg')
        or wind_data.get('metadata', {}).get('wind_direction_bin_width', 360.0 / max(n_directions, 1))
    )

    direction_contributions: List[Dict[str, Any]] = []
    direction_aep_wh = np.zeros(n_directions, dtype=float)
    direction_frequencies = np.sum(profile_prob_3d, axis=(0, 1))
    for direction_idx in range(n_directions):
        energy_wh = 0.0
        for profile_idx in range(n_power_profiles):
            energy_wh += float(
                np.sum(profile_powers_interp[profile_idx] * profile_prob_3d[profile_idx, :, direction_idx])
            ) * HOURS_PER_YEAR
        direction_aep_wh[direction_idx] = energy_wh
        direction_contributions.append({
            'direction_id': int(direction_idx + 1),
            'direction_center_rad': float(np.deg2rad(direction_centers_deg[direction_idx])),
            'direction_bin_width_rad': float(np.deg2rad(direction_bin_width_deg)),
            'frequency': float(direction_frequencies[direction_idx]),
            **_energy_fields(energy_wh),
        })

    # Compute per-wind-speed-bin breakdown.
    wind_speed_contributions: List[Dict[str, Any]] = []
    speed_aep_wh = np.zeros(wind_bin_count, dtype=float)
    speed_frequencies = np.sum(profile_prob_3d, axis=(0, 2))
    for speed_idx in range(wind_bin_count):
        energy_wh = 0.0
        for profile_idx in range(n_power_profiles):
            prob_at_speed = float(np.sum(profile_prob_3d[profile_idx, speed_idx, :]))
            energy_wh += profile_powers_interp[profile_idx][speed_idx] * prob_at_speed * HOURS_PER_YEAR
        speed_aep_wh[speed_idx] = energy_wh
        wind_speed_contributions.append({
            'wind_speed_bin_id': int(speed_idx + 1),
            'wind_speed_m_s': float(wind_bin_centers[speed_idx]),
            'frequency': float(speed_frequencies[speed_idx]),
            **_energy_fields(energy_wh),
        })

    # Compute profile-direction contribution matrix as flattened records.
    profile_direction_contributions: List[Dict[str, Any]] = []
    for profile_idx, profile_id in enumerate(profile_ids):
        for direction_idx in range(n_directions):
            directional_prob = profile_prob_3d[profile_idx, :, direction_idx]
            energy_wh = float(np.sum(profile_powers_interp[profile_idx] * directional_prob) * HOURS_PER_YEAR)
            profile_direction_contributions.append({
                'profile_id': int(profile_id),
                'direction_id': int(direction_idx + 1),
                'direction_center_rad': float(np.deg2rad(direction_centers_deg[direction_idx])),
                'frequency': float(np.sum(directional_prob)),
                **_energy_fields(energy_wh),
            })

    # Compute profile-direction-wind-speed contribution matrix as flattened records.
    profile_direction_wind_speed_contributions: List[Dict[str, Any]] = []
    for profile_idx, profile_id in enumerate(profile_ids):
        for direction_idx in range(n_directions):
            for speed_idx in range(wind_bin_count):
                probability = float(profile_prob_3d[profile_idx, speed_idx, direction_idx])
                energy_wh = float(profile_powers_interp[profile_idx][speed_idx] * probability * HOURS_PER_YEAR)
                profile_direction_wind_speed_contributions.append({
                    'profile_id': int(profile_id),
                    'direction_id': int(direction_idx + 1),
                    'direction_center_rad': float(np.deg2rad(direction_centers_deg[direction_idx])),
                    'wind_speed_bin_id': int(speed_idx + 1),
                    'wind_speed_m_s': float(wind_bin_centers[speed_idx]),
                    'frequency': probability,
                    **_energy_fields(energy_wh),
                })
    
    # Calculate rated power and capacity factor
    all_powers = []
    for curve in power_curves:
        all_powers.extend(curve['cycle_power_w'])
    rated_power = max(all_powers) if all_powers else 0.0
    
    average_power = total_aep_wh / HOURS_PER_YEAR
    capacity_factor = average_power / rated_power if rated_power > 0 else 0

    max_rated_idx = int(np.argmax(profile_rated_powers)) if profile_rated_powers.size > 0 else 0
    max_rated_power_w = float(profile_rated_powers[max_rated_idx]) if profile_rated_powers.size > 0 else 0.0
    max_rated_wind_speed_m_s = (
        float(profile_rated_wind_speeds[max_rated_idx]) if profile_rated_wind_speeds.size > 0 else 0.0
    )
    
    return {
        'metadata': {
            'name': 'Annual Energy Production',
            'description': 'AEP calculated from power curves and wind-resource probabilities',
            'note': 'None',
            'awesIO_version': 'None',
            'schema': 'aep_schema.yml',
            'time_created': datetime.now().isoformat(),
        },
        'inputs': {
            'power_curve_metadata': power_data.get('metadata', {}),
            'wind_resource_metadata': wind_data.get('metadata', {}),
        },
        'power_summary': {
            'capacity_factor': float(capacity_factor),
            'max_rated_power_w': max_rated_power_w,
            'max_rated_power_wind_speed_m_s': max_rated_wind_speed_m_s,
            'mean_power_w': float(average_power),
            'profiles': [
                {
                    'profile_id': int(profile_id),
                    'rated_power_w': float(rated_power_w),
                    'rated_wind_speed_m_s': float(rated_wind_speed_m_s),
                }
                for profile_id, rated_power_w, rated_wind_speed_m_s in zip(
                    profile_ids, profile_rated_powers, profile_rated_wind_speeds
                )
            ],
        },
        'annual_energy_production': {
            'total': {
                'aep_mwh': float(total_aep_wh / 1e6),
            },
            'by_profile': profile_contributions,
            'by_direction': direction_contributions,
            'by_wind_speed': wind_speed_contributions,
            'by_profile_and_direction': profile_direction_contributions,
            'by_profile_and_direction_and_wind_speed': profile_direction_wind_speed_contributions,
        },
    }


def _generate_aep_plots(aep_results: Dict[str, Any],
                        power_data: Dict[str, Any],
                        wind_data: Dict[str, Any],
                        output_dir: Optional[Path] = None) -> None:
    """Generate comprehensive AEP analysis plots.
    
    Args:
        aep_results: AEP calculation results.
        power_data: Power curve data.
        wind_data: Wind resource data.
        output_dir: Directory to save plots. If None, plots are shown but not saved.
    """
    # Create figure with multiple subplots
    fig = plt.figure(figsize=(18, 15))
    
    # 1. Cluster AEP contribution pie chart
    ax1 = plt.subplot(3, 3, 1)
    _plot_cluster_aep_contribution(ax1, aep_results)
    
    # 2. Cluster frequency bar chart
    ax2 = plt.subplot(3, 3, 2)
    _plot_cluster_frequency(ax2, aep_results, wind_data)
    
    # 3. Aggregate power curve
    ax3 = plt.subplot(3, 3, 3)
    _plot_aggregate_power_curve(ax3, power_data)
    
    # 4. Cluster power curves
    ax4 = plt.subplot(3, 3, 4)
    _plot_cluster_power_curves(ax4, power_data)
    
    # 5. Wind speed probability distribution
    ax5 = plt.subplot(3, 3, 5)
    _plot_wind_speed_distribution(ax5, wind_data)
    
    # 6. Capacity factor summary
    ax6 = plt.subplot(3, 3, 6)
    _plot_capacity_factor_summary(ax6, aep_results)
    
    # 7. Wind rose - power by direction
    ax7 = plt.subplot(3, 3, 7, projection='polar')
    _plot_wind_rose_power(ax7, power_data, wind_data, aep_results)
    
    # 8. Wind rose - frequency by direction
    ax8 = plt.subplot(3, 3, 8, projection='polar')
    _plot_wind_rose_frequency(ax8, wind_data)
    
    plt.tight_layout()
    
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        save_path = output_dir / "aep_analysis_complete.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    else:
        plt.show()


def _plot_cluster_aep_contribution(ax, aep_results: Dict[str, Any]) -> None:
    """Plot pie chart of cluster AEP contributions."""
    contributions = aep_results['annual_energy_production']['by_profile']
    cluster_ids = [c['profile_id'] for c in contributions]
    aep_values = [c['aep_mwh'] for c in contributions]
    
    ax.pie(aep_values, labels=cluster_ids, autopct='%1.1f%%', startangle=90)
    ax.set_title('AEP Contribution by Cluster')


def _plot_cluster_frequency(ax, aep_results: Dict[str, Any], 
                            wind_data: Dict[str, Any]) -> None:
    """Plot bar chart of cluster frequencies."""
    # Calculate frequency from probability matrix
    probability_matrix = np.array(wind_data['probability_matrix']['data'])
    
    # Handle both 2D and 3D probability matrices
    if probability_matrix.ndim == 3:
        cluster_frequencies = np.sum(probability_matrix, axis=(1, 2)) / 100.0
    else:
        cluster_frequencies = np.sum(probability_matrix, axis=1) / 100.0
        
    cluster_ids = [f"C{i+1}" for i in range(len(cluster_frequencies))]
    
    ax.bar(cluster_ids, cluster_frequencies * 100)
    ax.set_xlabel('Cluster ID')
    ax.set_ylabel('Frequency (%)')
    ax.set_title('Cluster Occurrence Frequency')
    ax.grid(True, alpha=0.3)


def _plot_aggregate_power_curve(ax, power_data: Dict[str, Any]) -> None:
    """Plot aggregate power curve."""
    if 'reference_wind_speeds' not in power_data or 'power_curves' not in power_data:
        raise ValueError(
            "Unsupported power curve format for plotting. Expected 'reference_wind_speeds' and 'power_curves'."
        )

    wind_speeds = np.array(power_data['reference_wind_speeds'])
    powers = np.array(power_data['power_curves'][0]['cycle_power_w']) / 1000  # Convert to kW
    max_power = max(powers)
    
    ax.plot(wind_speeds, powers, 'b-', linewidth=2, label='Power Curve')
    ax.axhline(y=max_power, color='r', linestyle='--', label='Rated Power')
    ax.set_xlabel('Wind Speed (m/s)')
    ax.set_ylabel('Power (kW)')
    ax.set_title('Aggregate Power Curve')
    ax.grid(True, alpha=0.3)
    ax.legend()


def _plot_cluster_power_curves(ax, power_data: Dict[str, Any]) -> None:
    """Plot all cluster power curves."""
    if 'reference_wind_speeds' not in power_data or 'power_curves' not in power_data:
        raise ValueError(
            "Unsupported power curve format for plotting. Expected 'reference_wind_speeds' and 'power_curves'."
        )

    wind_speeds = np.array(power_data['reference_wind_speeds'])
    for curve in power_data['power_curves']:
        powers = np.array(curve['cycle_power_w']) / 1000  # Convert to kW
        ax.plot(wind_speeds, powers, alpha=0.7,
                label=f"Profile {curve['profile_id']}")
    
    ax.set_xlabel('Wind Speed (m/s)')
    ax.set_ylabel('Power (kW)')
    ax.set_title('Power Curves')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)



def _plot_wind_speed_distribution(ax, wind_data: Dict[str, Any]) -> None:
    """Plot wind speed probability distribution."""
    probability_matrix = np.array(wind_data['probability_matrix']['data'])
    _wind_speed_bins = wind_data['wind_speed_bins']
    bin_centers = np.array(
        _wind_speed_bins.get('bin_centers_m_s',
        _wind_speed_bins.get('bin_centers', []))
    )
    
    # Sum across all clusters (and wind directions if 3D) to get overall distribution
    if probability_matrix.ndim == 3:
        total_distribution = np.sum(probability_matrix, axis=(0, 2)) / 100.0
    else:
        total_distribution = np.sum(probability_matrix, axis=0) / 100.0
    
    # Calculate bar width from bin spacing for clean visualization
    if len(bin_centers) > 1:
        bar_width = np.mean(np.diff(bin_centers)) * 0.9
    else:
        bar_width = 0.5
    
    ax.bar(bin_centers, total_distribution, width=bar_width, alpha=0.7, color='steelblue', edgecolor='navy')
    ax.set_xlabel('Wind Speed (m/s)')
    ax.set_ylabel('Probability')
    ax.set_title('Overall Wind Speed Distribution')
    ax.grid(True, alpha=0.3, axis='y')


def _plot_capacity_factor_summary(ax, aep_results: Dict[str, Any]) -> None:
    """Plot capacity factor summary as a bar chart."""
    power_summary = aep_results['power_summary']
    cf = power_summary['capacity_factor'] * 100
    mean_power = power_summary['mean_power_w'] / 1000.0
    rated_power = power_summary['max_rated_power_w'] / 1000.0
    
    labels = ['Average Power',  'Rated Power\n(Max)']
    values = [mean_power, rated_power]
    colors = ['green', 'blue']
    
    bars = ax.barh(labels, values, color=colors, alpha=0.7)
    ax.set_xlabel('Power (kW)')
    ax.set_title(f'Power Summary - Capacity Factor: {cf:.1f}%')
    ax.grid(True, alpha=0.3, axis='x')
    
    # Add text annotations
    for i, (val, bar) in enumerate(zip(values, bars)):
        ax.text(val, i, f' {val:.1f} kW', va='center', ha='left', fontsize=9, fontweight='bold')


def _plot_wind_rose_power(ax, power_data: Dict[str, Any], wind_data: Dict[str, Any], 
                          aep_results: Dict[str, Any]) -> None:
    """Plot wind rose showing power contribution by wind direction."""
    probability_matrix = np.array(wind_data['probability_matrix']['data'])
    
    # Check if we have directional data
    if probability_matrix.ndim < 3:
        ax.text(0.5, 0.5, 'No directional\ndata available', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
        ax.set_title('Power by Wind Direction')
        return
    
    if 'reference_wind_speeds' not in power_data or 'power_curves' not in power_data:
        raise ValueError(
            "Unsupported power curve format for plotting. Expected 'reference_wind_speeds' and 'power_curves'."
        )

    # Get wind speeds and power values
    wind_speeds = np.array(power_data['reference_wind_speeds'])
    powers = np.array(power_data['power_curves'][0]['cycle_power_w'])
    
    # Calculate power contribution per direction
    # Sum across all clusters and wind speeds, weighted by probability and power
    n_directions = probability_matrix.shape[2]
    power_by_direction = np.zeros(n_directions)
    
    _wsb = wind_data['wind_speed_bins']
    wind_bin_centers = np.array(
        _wsb.get('bin_centers_m_s', _wsb.get('bin_centers', []))
    )
    powers_interp = np.interp(wind_bin_centers, wind_speeds, powers)
    
    for d in range(n_directions):
        # Sum across clusters and wind speeds
        direction_prob = probability_matrix[:, :, d] / 100.0  # Convert % to fraction
        power_by_direction[d] = np.sum(direction_prob * powers_interp[np.newaxis, :])
    
    # Convert to kW and normalize for visualization
    power_by_direction_kw = power_by_direction / 1000.0
    
    # Wind directions in radians (0 = North, clockwise)
    direction_bin_width = (
        wind_data['metadata'].get('wind_direction_bin_width_deg') or
        wind_data['metadata'].get('wind_direction_bin_width', 36.0)
    )
    theta = np.linspace(0, 2 * np.pi, n_directions, endpoint=False)
    width = np.deg2rad(direction_bin_width)
    
    # Create polar bar plot
    bars = ax.bar(theta, power_by_direction_kw, width=width, bottom=0.0, alpha=0.7, 
                   edgecolor='black', linewidth=0.5)
    
    # Color bars by magnitude
    colors = plt.cm.YlOrRd(power_by_direction_kw / power_by_direction_kw.max())
    for bar, color in zip(bars, colors):
        bar.set_facecolor(color)
    
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_title('Power Contribution by Wind Direction', pad=20)
    ax.set_ylabel('Power (kW)', labelpad=30)


def _plot_wind_rose_frequency(ax, wind_data: Dict[str, Any]) -> None:
    """Plot wind rose showing wind frequency by direction."""
    probability_matrix = np.array(wind_data['probability_matrix']['data'])
    
    # Check if we have directional data
    if probability_matrix.ndim < 3:
        ax.text(0.5, 0.5, 'No directional\ndata available', 
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
        ax.set_title('Wind Frequency by Direction')
        return
    
    # Sum across clusters and wind speeds to get frequency per direction
    n_directions = probability_matrix.shape[2]
    freq_by_direction = np.sum(probability_matrix, axis=(0, 1)) / 100.0  # Convert % to fraction
    
    # Wind directions in radians (0 = North, clockwise)
    direction_bin_width = (
        wind_data['metadata'].get('wind_direction_bin_width_deg') or
        wind_data['metadata'].get('wind_direction_bin_width', 36.0)
    )
    theta = np.linspace(0, 2 * np.pi, n_directions, endpoint=False)
    width = np.deg2rad(direction_bin_width)
    
    # Create polar bar plot
    bars = ax.bar(theta, freq_by_direction * 100, width=width, bottom=0.0, alpha=0.7,
                   edgecolor='black', linewidth=0.5)
    
    # Color bars by magnitude
    colors = plt.cm.Blues(freq_by_direction / freq_by_direction.max())
    for bar, color in zip(bars, colors):
        bar.set_facecolor(color)
    
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_title('Wind Frequency by Direction', pad=20)
    ax.set_ylabel('Frequency (%)', labelpad=30)

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class SplitConfig:
    threshold: int = 0
    padding: int = 3
    min_component_area: int = 8
    direction_window: int = 4
    split_angle_deg: float = 55.0
    min_segment_points: int = 5
    bridge_radius: int = 1
    bridge_collapse_len: int = 0
    short_segment_force_merge: int = 3
    merge_angle_deg: float = 28.0
    through_angle_deg: float = 32.0
    max_endpoint_gap: float = 2.5
    tiny_segment_points: int = 8
    tiny_merge_distance: float = 1.5
    min_region_area: int = 10
    overlap_margin: float = 1.35
    fold_attach_angle_deg: float = 45.0
    fold_attach_dir_tol_deg: float = 30.0
    fold_attach_gap_max: float = 6.0

    def to_dict(self) -> dict:
        return asdict(self)
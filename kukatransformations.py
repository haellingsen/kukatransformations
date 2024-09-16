import numpy as np
import pyvista as pv
import re

def parse_pose_string(pose_str):
    """Parse a pose string in the format '{X 101.00, Y -0.00, Z 2200.00, A 90.00, B -10.00, C -90.00}'"""
    pattern = r'{X ([-\d.]+), Y ([-\d.]+), Z ([-\d.]+), A ([-\d.]+), B ([-\d.]+), C ([-\d.]+)}'
    match = re.match(pattern, pose_str)
    if match:
        return tuple(map(float, match.groups()))
    else:
        raise ValueError("Invalid pose string format")


def create_transformation_matrix(x, y, z, a, b, c):
    """Create a 4x4 transformation matrix from KUKA KRL coordinates."""
    a, b, c = np.radians([a, b, c])
    
    Rz = np.array([[np.cos(a), -np.sin(a), 0], 
                   [np.sin(a), np.cos(a), 0], 
                   [0, 0, 1]])
    
    Ry = np.array([[np.cos(b), 0, np.sin(b)], 
                   [0, 1, 0], 
                   [-np.sin(b), 0, np.cos(b)]])
    
    Rx = np.array([[1, 0, 0], 
                   [0, np.cos(c), -np.sin(c)], 
                   [0, np.sin(c), np.cos(c)]])
    
    R = Rz @ Ry @ Rx
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [x, y, z]
    return T

def extract_pose_parameters(T):
    """Extract X, Y, Z, A, B, C from a transformation matrix."""
    x, y, z = T[:3, 3]
    
    # Extract Euler angles
    sy = np.sqrt(T[0, 0] * T[0, 0] + T[1, 0] * T[1, 0])
    singular = sy < 1e-6
    
    if not singular:
        a = np.arctan2(T[1, 0], T[0, 0])
        b = np.arctan2(-T[2, 0], sy)
        c = np.arctan2(T[2, 1], T[2, 2])
    else:
        a = np.arctan2(-T[1, 2], T[1, 1])
        b = np.arctan2(-T[2, 0], sy)
        c = 0
    
    return x, y, z, np.degrees(a), np.degrees(b), np.degrees(c)

def invert_transformation(T):
    """Invert a homogeneous transformation matrix."""
    return np.linalg.inv(T)

def chain_poses(poses):
    """Chain multiple poses by applying matrix multiplication of all poses."""
    chained_poses = []
    current_T = np.eye(4)


    
    for pose, invert in poses:

        if isinstance(pose, str):
            pose = parse_pose_string(pose)

        T = create_transformation_matrix(*pose)
        if invert:
            T = invert_transformation(T)
        current_T = current_T @ T
        chained_poses.append((current_T.copy(), invert))
    
    return chained_poses

def calculate_extents(chained_poses):
    """Calculate the extents of all poses."""
    all_points = np.vstack([T[:3, 3] for T, _ in chained_poses])
    min_point = np.min(all_points, axis=0)
    max_point = np.max(all_points, axis=0)
    return min_point, max_point

def calculate_camera_position(min_point, max_point):
    """Calculate a suitable camera position based on the extents."""
    center = (min_point + max_point) / 2
    max_range = np.max(max_point - min_point)
    camera_distance = max_range * 2  # Adjust this multiplier as needed
    camera_position = center + np.array([1, 1, 1]) * camera_distance
    return camera_position, center
def create_coordinate_frame(scale=1.0):
    """Create a coordinate frame for visualization."""
    origin = np.array([0, 0, 0])
    x_axis = np.array([scale, 0, 0])
    y_axis = np.array([0, scale, 0])
    z_axis = np.array([0, 0, scale])
    
    frame = pv.PolyData()
    frame.points = np.vstack((origin, x_axis, y_axis, z_axis))
    frame.lines = np.array([[2, 0, 1], [2, 0, 2], [2, 0, 3]])
    
    return frame

def calculate_scene_size(chained_poses):
    """Calculate the overall size of the scene."""
    all_points = np.vstack([T[:3, 3] for T, _ in chained_poses])
    min_point = np.min(all_points, axis=0)
    max_point = np.max(all_points, axis=0)
    return np.linalg.norm(max_point - min_point)

def visualize_poses(poses):
    chained_poses = chain_poses(poses)
    
    plotter = pv.Plotter()
    plotter.set_background('black')
    
    # Calculate scene size and frame scale
    scene_size = calculate_scene_size(chained_poses)
    frame_scale = scene_size * 0.1  # Adjust this factor to change relative size of frames
    
    # Calculate and add extents
    min_point, max_point = calculate_extents(chained_poses)
    extents = pv.Box(bounds=(min_point[0] - 500, max_point[0] + 500,
                             min_point[1] - 500, max_point[1] + 500,
                             min_point[2] - 500, max_point[2] + 500))
    plotter.add_mesh(extents, style='wireframe', color='gray', line_width=1, opacity=0.5)
    
    for i, (T, invert) in enumerate(chained_poses):
        # Create coordinate frame
        frame = create_coordinate_frame(scale=frame_scale)
        frame.transform(T)
        
        # Add coordinate frame to the plot
        plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 0] * frame_scale), color='red', line_width=3)
        plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 1] * frame_scale), color='green', line_width=3)
        plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 2] * frame_scale), color='blue', line_width=3)
        
        # Add text label
        label_color = 'purple' if invert else 'white'
        plotter.add_point_labels(T[:3, 3].reshape(1, -1), [f'Pose {i+1}{"*" if invert else ""}'], 
                                 point_size=0, shape_opacity=0, font_size=30, text_color=label_color)
        
        # Connect poses with lines
        if i > 0:
            prev_T = chained_poses[i-1][0]
            line = pv.Line(prev_T[:3, 3], T[:3, 3])
            plotter.add_mesh(line, color='white', line_width=2)
        
        # Extract and print pose parameters
        x, y, z, a, b, c = extract_pose_parameters(T)
        invert_text = " (Inverted)" if invert else ""
        print(f"Pose {i+1}{invert_text}: {{X {x:.2f}, Y {y:.2f}, Z {z:.2f}, A {a:.2f}, B {b:.2f}, C {c:.2f}}}")
    
    # Set up the camera
    camera_position, focal_point = calculate_camera_position(min_point, max_point)
    plotter.camera_position = [tuple(camera_position), tuple(focal_point), (0, 0, 1)]
    plotter.show_axes()
    
    plotter.show()


poses = [
    ((0, 0, 22, 90, -10, -90), False), 
    ((0, 0, 101, 0, 0, 0), True),    
    ((3000, 0, 4, 0, 90, 0), False), 
    ((0, 0, 0, 0, 0, 0), False), 
]

kuka_poses = [
    (
        "{X -350.50, Y 2, Z 2, A 0.00, B 0.00, C -80.00}"
        , False),
(
        "{X 3000.00, Y -0.00, Z 45, A 0.00, B 90.00, C 0.00}"
        , True),
]

#visualize_poses(kuka_poses)
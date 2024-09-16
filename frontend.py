import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLineEdit, QListWidget, QCheckBox, QLabel, QListWidgetItem
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

# Import functions from kukatransformations.py
from kukatransformations import (
    parse_pose_string, create_transformation_matrix, extract_pose_parameters,
    invert_transformation, chain_poses, calculate_extents,
    calculate_camera_position, create_coordinate_frame, calculate_scene_size
)

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.main_window = None

    def set_main_window(self, main_window):
        self.main_window = main_window
        print(f"Main window set: {self.main_window}")  # Debug print

    def dropEvent(self, event: QDropEvent):
        print("Drop event started")  # Debug print
        super().dropEvent(event)
        if self.main_window:
            print("Calling update_poses_from_list")  # Debug print
            self.main_window.update_poses_from_list()
        else:
            print("Main window not set")  # Debug print
        print("Drag and drop occurred, updating poses list")

class KUKAPoseVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KUKA Pose Visualizer")
        self.setGeometry(100, 100, 1000, 600)

        self.poses = [
            ((-350.50, 2954.42, 2720.94, 0.00, -0.00, -80.00), False),
            ((101.00, -0.00, 2200.00, 90.00, -10.00, -90.00), False),
            ((3000.00, -0.00,  451.5, 0.00, 90.00, 0.00), False)
        ]
        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left panel for input and pose list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Input for new pose
        self.pose_input = QLineEdit()
        self.pose_input.setPlaceholderText("{X 0.00, Y 0.00, Z 0.00, A 0.00, B 0.00, C 0.00}")
        self.pose_input.returnPressed.connect(self.add_pose)  # Connect Enter key to add_pose
        left_layout.addWidget(self.pose_input)

        # Checkbox for invert
        self.invert_checkbox = QCheckBox("Invert")
        left_layout.addWidget(self.invert_checkbox)

        # Button to add pose
        add_button = QPushButton("Add Pose")
        add_button.clicked.connect(self.add_pose)
        left_layout.addWidget(add_button)

        # List of poses
        self.pose_list = DraggableListWidget()
        self.pose_list.set_main_window(self)
        self.pose_list.itemDoubleClicked.connect(self.toggle_invert_pose)
        left_layout.addWidget(self.pose_list)

        # Button to remove selected pose
        remove_button = QPushButton("Remove Selected Pose")
        remove_button.clicked.connect(self.remove_pose)
        left_layout.addWidget(remove_button)

        # Button to visualize poses
        visualize_button = QPushButton("Visualize Poses")
        visualize_button.clicked.connect(self.visualize_poses)
        left_layout.addWidget(visualize_button)

        # Add resulting pose display
        self.result_label = QLabel("Resulting Pose: ")
        left_layout.addWidget(self.result_label)

        main_layout.addWidget(left_panel)

        # Right panel for visualization
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.plotter = QtInteractor(self)
        right_layout.addWidget(self.plotter.interactor)

        main_layout.addWidget(right_panel)
        self.update_pose_list()

    def add_pose(self):
        pose_str = self.pose_input.text()
        try:
            pose = parse_pose_string(pose_str)
            inverted = self.invert_checkbox.isChecked()
            self.poses.append((pose, inverted))
            self.update_pose_list()
            self.pose_input.clear()
            self.invert_checkbox.setChecked(False)
        except ValueError as e:
            print(f"Error: {e}")

    def remove_pose(self):
        current_row = self.pose_list.currentRow()
        if current_row >= 0:
            del self.poses[current_row]
            self.update_pose_list()
    
    def toggle_invert_pose(self, item):
        row = self.pose_list.row(item)
        pose, inverted = self.poses[row]
        self.poses[row] = (pose, not inverted)
        self.update_pose_list()
        # Restore the selection after updating the list
        self.pose_list.setCurrentRow(row)

    def update_poses_from_list(self):
        new_poses = []
        for i in range(self.pose_list.count()):
            item = self.pose_list.item(i)
            text = item.text()
            print(text)
            pose_str, _ , inverted_str = text.partition('}')
            pose = parse_pose_string(pose_str+_)
            print(pose)
            inverted = '(Inverted)' in inverted_str
            new_poses.append((pose, inverted))
        self.poses = new_poses
        self.visualize_poses()
        print("Updated poses order:", [f"Pose {i+1}" for i in range(len(self.poses))])  # Debug print

    def update_pose_list(self):
        current_selection = self.pose_list.currentRow()
        self.pose_list.clear()
        for i, (pose, inverted) in enumerate(self.poses):
            pose_str = "{X %.2f, Y %.2f, Z %.2f, A %.2f, B %.2f, C %.2f}" % pose
            item = QListWidgetItem(f"{pose_str} {'(Inverted)' if inverted else ''}")
            self.pose_list.addItem(item)
        if current_selection != -1 and current_selection < self.pose_list.count():
            self.pose_list.setCurrentRow(current_selection)
        self.visualize_poses()
        
    def visualize_poses(self):
        self.plotter.clear()
        
        chained_poses = chain_poses(self.poses)
        
        # Calculate scene size and frame scale
        scene_size = calculate_scene_size(chained_poses)
        frame_scale = scene_size * 0.1

        # Calculate and add extents
        min_point, max_point = calculate_extents(chained_poses)
        extents = pv.Box(bounds=(min_point[0] - 500, max_point[0] + 500,
                                 min_point[1] - 500, max_point[1] + 500,
                                 min_point[2] - 500, max_point[2] + 500))
        self.plotter.add_mesh(extents, style='wireframe', color='gray', line_width=1, opacity=0.5)

        for i, (T, invert) in enumerate(chained_poses):
            # Create coordinate frame
            frame = create_coordinate_frame(scale=frame_scale)
            frame.transform(T)
            
            # Add coordinate frame to the plot
            self.plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 0] * frame_scale), color='red', line_width=3)
            self.plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 1] * frame_scale), color='green', line_width=3)
            self.plotter.add_mesh(pv.Line(T[:3, 3], T[:3, 3] + T[:3, 2] * frame_scale), color='blue', line_width=3)
            
            # Add text label
            label_color = 'purple' if invert else 'black'
            self.plotter.add_point_labels(T[:3, 3].reshape(1, -1), [f'Pose {i+1}{"*" if invert else ""}'], 
                                          point_size=0, shape_opacity=0, font_size=30, text_color=label_color)
            
            # Connect poses with lines
            if i > 0:
                prev_T = chained_poses[i-1][0]
                line = pv.Line(prev_T[:3, 3], T[:3, 3])
                self.plotter.add_mesh(line, color='white', line_width=2)

        # Calculate and display the resulting pose
        if chained_poses:
            final_transformation = chained_poses[-1][0]
            x, y, z, a, b, c = extract_pose_parameters(final_transformation)
            result_str = f"Resulting Pose: {{X {x:.2f}, Y {y:.2f}, Z {z:.2f}, A {a:.2f}, B {b:.2f}, C {c:.2f}}}"
            self.result_label.setText(result_str)
            print(result_str)  # Debug print
        else:
            self.result_label.setText("Resulting Pose: No poses to visualize")
        
        # Set up the camera
        camera_position, focal_point = calculate_camera_position(min_point, max_point)
        self.plotter.camera_position = [tuple(camera_position), tuple(focal_point), (0, 0, 1)]
        self.plotter.reset_camera()
        self.plotter.show_axes()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = KUKAPoseVisualizer()
    window.show()
    sys.exit(app.exec_())
import sys
from PyQt5.QtCore import QItemSelection, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QWidget, QPushButton, 
                             QLineEdit, QListWidget, QCheckBox, QLabel, 
                             QListWidgetItem, QInputDialog, QDialog,
                             QMessageBox, QApplication)
from PyQt5.QtGui import QDropEvent, QCursor
import pyvista as pv
from pyvistaqt import QtInteractor

# Import functions from kukatransformations.py
from kukatransformations import (
    parse_pose_string, extract_pose_parameters, chain_poses, calculate_extents,
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

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        ## debug print currently selected item
        return super().selectionChanged(selected, deselected)

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
        self.last_scene_size = None
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
        self.pose_list.itemDoubleClicked.connect(self.edit_pose)
        left_layout.addWidget(self.pose_list)

        # Button to remove selected pose
        remove_button = QPushButton("Remove Selected Pose")
        remove_button.clicked.connect(self.remove_pose)
        left_layout.addWidget(remove_button)

        # Button to invert selected pose
        self.invert_button = QPushButton("Invert Pose")
        self.invert_button.clicked.connect(lambda: self.toggle_invert_pose())
        left_layout.addWidget(self.invert_button)

        # Button to visualize poses
        visualize_button = QPushButton("Visualize Poses")
        visualize_button.clicked.connect(self.visualize_poses)
        left_layout.addWidget(visualize_button)

        # Add resulting pose display
        self.result_label = QLabel("Resulting Pose: ")
        self.result_label.mousePressEvent = self.copy_result_to_clipboard  # Add click event
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
            print(f"ValueError: {e}")

    def remove_pose(self):
        current_row = self.pose_list.currentRow()
        if current_row >= 0:
            del self.poses[current_row]
            self.update_pose_list()

    def edit_pose(self, item):
        current_text = item.text()
        current_row = self.pose_list.row(item)
        
        # Create a custom dialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Edit Pose")
        dialog.setLabelText("Enter new pose:")
        dialog.setTextValue(current_text)
        dialog.setInputMode(QInputDialog.TextInput)
        
        # Set the size of the dialog
        dialog.resize(1000, dialog.height())
        
        # Set the minimum width of the text field
        text_field = dialog.findChild(QLineEdit)
        if text_field:
            text_field.setMinimumWidth(900)
        
        if dialog.exec_() == QDialog.Accepted:
            new_text = dialog.textValue()
            if new_text:
                try:
                    # Attempt to parse the new pose string
                    pose_str, _, inverted_str = new_text.partition('}')
                    new_pose = parse_pose_string(pose_str + _)
                    inverted = '(Inverted)' in inverted_str
                    
                    # If parsing succeeds, update the pose in self.poses
                    self.poses[current_row] = (new_pose, inverted)
                    
                    # Update the item text
                    item.setText(new_text)
                    
                    # Update the visualization
                    self.update_poses_from_list(False)
                    
                except ValueError as e:
                    print(f"Invalid pose format: {e}")
                    # Show an error message to the user
                    QMessageBox.warning(self, "Invalid Pose", f"The entered pose is invalid: {e}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    QMessageBox.warning(self, "Error", f"An unexpected error occurred: {e}")

    def copy_result_to_clipboard(self, event):
        if event.button() == Qt.LeftButton:
            clipboard = QApplication.clipboard()
            text = self.result_label.text().split(": ", 1)[-1]  # Get only the pose part
            clipboard.setText(text)
            self.show_copied_message()

    def show_copied_message(self):
        original_text = self.result_label.text()
        self.result_label.setText("Copied to clipboard!")
        QApplication.processEvents()  # Force update of the UI
        QTimer.singleShot(1500, lambda: self.result_label.setText(original_text))

    def toggle_invert_pose(self):
        selected_rows = self.pose_list.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            pose, inverted = self.poses[row]
            self.poses[row] = (pose, not inverted)
            self.update_pose_list()
            # Restore the selection after updating the list
            self.pose_list.setCurrentRow(row)

    def update_poses_from_list(self, _update_zoom=True):
        try:
            new_poses = []
            for i in range(self.pose_list.count()):
                item = self.pose_list.item(i)
                text = item.text()
                pose_str, _ , inverted_str = text.partition('}')
                pose = parse_pose_string(pose_str+_)
                inverted = '(Inverted)' in inverted_str
                new_poses.append((pose, inverted))
        except Exception as e:
            print(f"Error updating poses from list: {e}")
            raise Exception(e)
            return
        self.poses = new_poses
        self.visualize_poses(update_zoom=_update_zoom)
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

    def visualize_poses(self, add_extent_bounds=False, update_zoom=True):
        self.plotter.clear()

        chained_poses, resulting_pose = chain_poses(self.poses)
        # Update the resulting pose display
        
        # Extract and print pose parameters
        x, y, z, a, b, c = extract_pose_parameters(resulting_pose)
        resulting_pose_string = f"{{X {x:.2f}, Y {y:.2f}, Z {z:.2f}, A {a:.2f}, B {b:.2f}, C {c:.2f}}}"
        self.result_label.setText(f"Resulting Pose: {resulting_pose_string}")
        self.result_label.setToolTip(f"Click to copy: {resulting_pose_string}")
        
        # Calculate scene size and frame scale
        if update_zoom:
            scene_size = calculate_scene_size(chained_poses)
            frame_scale = scene_size * 0.1
            self.last_scene_size = scene_size

        if self.last_scene_size is not None:
            frame_scale = self.last_scene_size * 0.1

        # Calculate and add extents
        min_point, max_point = calculate_extents(chained_poses)
        extents = pv.Box(bounds=(min_point[0] - 500, max_point[0] + 500,
                                 min_point[1] - 500, max_point[1] + 500,
                                 min_point[2] - 500, max_point[2] + 500))
        if add_extent_bounds:
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
                self.plotter.add_mesh(line, color='black', line_width=1)
            
            # Extract and print pose parameters
            x, y, z, a, b, c = extract_pose_parameters(T)
            invert_text = " (Inverted)" if invert else ""
            print(f"Pose {i+1}{invert_text}: {{X {x:.2f}, Y {y:.2f}, Z {z:.2f}, A {a:.2f}, B {b:.2f}, C {c:.2f}}}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = KUKAPoseVisualizer()
    window.show()
    sys.exit(app.exec_())
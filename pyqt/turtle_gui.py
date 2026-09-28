import os
import sys
import threading

import pymysql
import rclpy as rp
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String
from std_srvs.srv import Trigger

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QGridLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

# DB 접속 정보는 코드에 넣지 않고 환경변수로 받습니다. (깃허브에 비밀번호가 올라가지 않도록)
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = 'rosdb'


class RosWorker(QObject):
    """ROS2 통신 담당. 별도 스레드에서 spin 하고, 결과는 시그널로 GUI에 전달."""

    status = pyqtSignal(str)
    pose_received = pyqtSignal(float, float, float)

    def __init__(self):
        super().__init__()
        rp.init()
        self.node = rp.create_node('turtle_gui_node')
        self.dir_pub = self.node.create_publisher(
            String, '/turtle_ctrl/direction', 10)
        self.reset_client = self.node.create_client(
            Trigger, '/turtle_ctrl/reset')
        self.pose_client = self.node.create_client(
            Trigger, '/turtle_ctrl/get_pose')

        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.thread.start()

    def send_direction(self, direction):
        msg = String()
        msg.data = direction
        self.dir_pub.publish(msg)
        self.status.emit('Move: ' + direction)

    def request_reset(self):
        if not self.reset_client.service_is_ready():
            self.status.emit('turtle_controller 노드가 실행 중인지 확인하세요.')
            return
        future = self.reset_client.call_async(Trigger.Request())
        future.add_done_callback(self._reset_done)

    def _reset_done(self, future):
        res = future.result()
        self.status.emit('Reset: ' + res.message)

    def request_pose(self):
        if not self.pose_client.service_is_ready():
            self.status.emit('turtle_controller 노드가 실행 중인지 확인하세요.')
            return
        future = self.pose_client.call_async(Trigger.Request())
        future.add_done_callback(self._pose_done)

    def _pose_done(self, future):
        res = future.result()
        if not res.success:
            self.status.emit('Pose 실패: ' + res.message)
            return
        x, y, theta = map(float, res.message.split(','))
        self.pose_received.emit(x, y, theta)

    def shutdown(self):
        self.executor.shutdown()
        self.node.destroy_node()
        rp.shutdown()


class TurtleGui(QWidget):

    def __init__(self):
        super().__init__()
        self.ros = RosWorker()
        self.ros.status.connect(self.show_status)
        self.ros.pose_received.connect(self.save_pose)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('ROS Turtle Control')

        self.btn_up = QPushButton('↑')
        self.btn_down = QPushButton('↓')
        self.btn_left = QPushButton('←')
        self.btn_right = QPushButton('→')
        self.btn_reset = QPushButton('Reset')
        self.btn_save = QPushButton('Save Position')
        self.label = QLabel('Ready')

        self.btn_up.clicked.connect(lambda: self.ros.send_direction('up'))
        self.btn_down.clicked.connect(lambda: self.ros.send_direction('down'))
        self.btn_left.clicked.connect(lambda: self.ros.send_direction('left'))
        self.btn_right.clicked.connect(lambda: self.ros.send_direction('right'))
        self.btn_reset.clicked.connect(self.ros.request_reset)
        self.btn_save.clicked.connect(self.ros.request_pose)

        grid = QGridLayout()
        grid.addWidget(self.btn_up, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_down, 1, 1)
        grid.addWidget(self.btn_right, 1, 2)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.btn_save)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def show_status(self, text):
        self.label.setText(text)

    def save_pose(self, x, y, theta):
        try:
            conn = pymysql.connect(host=DB_HOST, user=DB_USER,
                                   password=DB_PASSWORD, database=DB_NAME)
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO turtlepos (x, y, theta) VALUES (%s, %s, %s)',
                    (x, y, theta))
            conn.commit()
            conn.close()
            self.label.setText(
                'Saved: x=%.2f, y=%.2f, theta=%.2f' % (x, y, theta))
        except pymysql.MySQLError as e:
            self.label.setText('DB 오류: ' + str(e))

    def closeEvent(self, event):
        self.ros.shutdown()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = TurtleGui()
    gui.show()
    sys.exit(app.exec_())
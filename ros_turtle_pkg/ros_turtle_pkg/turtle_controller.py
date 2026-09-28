import rclpy as rp
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import String
from std_srvs.srv import Empty, Trigger
from turtlesim.msg import Pose

LINEAR_SPEED = 2.0    # 앞/뒤 이동 속도
ANGULAR_SPEED = 1.57  # 좌/우 회전 속도 (약 90도)


class TurtleController(Node):
    """PyQt 앱의 명령을 받아 거북이를 제어하는 노드.

    - /turtle_ctrl/direction (String) : up / down / left / right
    - /turtle_ctrl/reset     (Trigger): 거북이 리셋
    - /turtle_ctrl/get_pose  (Trigger): 현재 위치를 "x,y,theta" 문자열로 응답
    """

    def __init__(self):
        super().__init__('turtle_controller')
        self.current_pose = None

        self.cmd_pub = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        self.pose_sub = self.create_subscription(
            Pose, '/turtle1/pose', self.pose_callback, 10)
        self.dir_sub = self.create_subscription(
            String, '/turtle_ctrl/direction', self.direction_callback, 10)

        self.reset_srv = self.create_service(
            Trigger, '/turtle_ctrl/reset', self.reset_callback)
        self.pose_srv = self.create_service(
            Trigger, '/turtle_ctrl/get_pose', self.get_pose_callback)

        self.reset_client = self.create_client(Empty, '/reset')

        self.get_logger().info('Turtle controller is started.')

    def pose_callback(self, msg):
        self.current_pose = msg

    def direction_callback(self, msg):
        twist = Twist()

        if msg.data == 'up':
            twist.linear.x = LINEAR_SPEED
        elif msg.data == 'down':
            twist.linear.x = -LINEAR_SPEED
        elif msg.data == 'left':
            twist.angular.z = ANGULAR_SPEED
        elif msg.data == 'right':
            twist.angular.z = -ANGULAR_SPEED
        else:
            self.get_logger().warn('Unknown direction: ' + msg.data)
            return

        self.cmd_pub.publish(twist)

    def reset_callback(self, request, response):
        if not self.reset_client.service_is_ready():
            response.success = False
            response.message = 'turtlesim /reset service is not ready'
            return response

        # 서비스 콜백 안에서는 결과를 기다리지 않고 요청만 보냅니다.
        self.reset_client.call_async(Empty.Request())
        response.success = True
        response.message = 'reset requested'
        return response

    def get_pose_callback(self, request, response):
        if self.current_pose is None:
            response.success = False
            response.message = 'no pose received yet'
            return response

        p = self.current_pose
        response.success = True
        response.message = str(p.x) + ',' + str(p.y) + ',' + str(p.theta)
        return response


def main(args=None):
    rp.init(args=args)

    node = TurtleController()
    try:
        rp.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rp.shutdown()


if __name__ == '__main__':
    main()
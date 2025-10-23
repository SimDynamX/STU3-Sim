# DON'T CHANGE ANY OF THE BELOW; NECESSARY FOR JOINING SIMULATION
import os, sys, time, datetime, traceback
import spaceteams as st
def custom_exception_handler(exctype, value, tb):
    error_message = "".join(traceback.format_exception(exctype, value, tb))
    st.logger_fatal(error_message)
sys.excepthook = custom_exception_handler
st.connect_to_sim(sys.argv)
import numpy as np
# DON'T CHANGE ANY OF THE ABOVE; NECESSARY FOR JOINING SIMULATION
################################################################

st.OnScreenLogMessage("ROS_Telemetry started properly.", "ROS_Telemetry", st.Severity.Info)

import json
import roslibpy
import cv2


st.logger_info("Starting ROS Communication Server...")

try:
    ros = roslibpy.Ros(host='localhost', port=9090)
    ros.run()
except Exception as e:
    st.logger_error(f"Error connecting to ROS: {str(e)}")
    st.OnScreenLogMessage("ROS_Telemetry failed to connect to ROS. Please restart the sim after ROSBridge is running.", "ROS_Telemetry", st.Severity.Error)
    
    exit_flag = False
    while not exit_flag:
        # Loop forever just so we don't (sometimes) crash the sim by leaving early
        time.sleep(0.2)

    st.leave_sim()
    time.sleep(0.5) # Wait a bit so the messages send reliably before the socket closes
    exit(1)
st.logger_info("Connected to ROS")


this = st.GetThisSystem()
controlled_entity: st.Entity = this.GetParam(st.VarType.entityRef, "ControlledEntity")

# Reference frames
mars: st.Entity = this.GetParam(st.VarType.entityRef, "MarsReferenceFrame")
marsFrame = mars.GetBodyFixedFrame()
local: st.Entity = this.GetParam(st.VarType.entityRef, "LocalFrame")
localFrame = local.GetBodyFixedFrame()

##################################################### Sensors #####################################################
location_marsFrame_publisher = roslibpy.Topic(ros, '/LocationMarsFrame', 'geometry_msgs/Point')
velocity_marsFrame_publisher = roslibpy.Topic(ros, '/VelocityMarsFrame', 'geometry_msgs/Point')
rotation_marsFrame_publisher = roslibpy.Topic(ros, '/RotationMarsFrame', 'geometry_msgs/Quaternion')

location_localFrame_publisher = roslibpy.Topic(ros, '/LocationLocalFrame', 'geometry_msgs/Point')
velocity_localFrame_publisher = roslibpy.Topic(ros, '/VelocityLocalFrame', 'geometry_msgs/Point')
rotation_localFrame_publisher = roslibpy.Topic(ros, '/RotationLocalFrame', 'geometry_msgs/Quaternion')

def publish_location_and_rotation(deltaTime: float):
    loc_marsFrame = controlled_entity.getLocation().WRT_ExprIn(marsFrame)
    loc_prev_marsFrame = controlled_entity.GetParam(st.VarType.doubleV3, "LocationMarsFrame")
    rot_marsFrame = controlled_entity.getRotation().Quat_WRT(marsFrame)

    loc_localFrame = controlled_entity.getLocation().WRT_ExprIn(localFrame)
    loc_prev_localFrame = controlled_entity.GetParam(st.VarType.doubleV3, "LocationLocalFrame")
    rot_localFrame = controlled_entity.getRotation().Quat_WRT(localFrame)
    
    vel_marsFrame = np.zeros(3)
    vel_localFrame = np.zeros(3)
    if deltaTime != 0.0:
        vel_marsFrame = (loc_prev_marsFrame - loc_marsFrame) / deltaTime
        vel_localFrame = (loc_prev_localFrame - loc_localFrame) / deltaTime

    location_marsFrame_msg = roslibpy.Message({
        'x': loc_marsFrame[0],
        'y': loc_marsFrame[1],
        'z': loc_marsFrame[2]
    })
    
    velocity_marsFrame_msg = roslibpy.Message({
        'x': vel_marsFrame[0],
        'y': vel_marsFrame[1],
        'z': vel_marsFrame[2]
    })

    rotation_marsFrame_msg = roslibpy.Message({
        'x': rot_marsFrame[0],
        'y': rot_marsFrame[1],
        'z': rot_marsFrame[2],
        'w': rot_marsFrame[3]
    })

    location_localFrame_msg = roslibpy.Message({
        'x': loc_localFrame[0],
        'y': loc_localFrame[1],
        'z': loc_localFrame[2]
    })
    
    velocity_localFrame_msg = roslibpy.Message({
        'x': vel_localFrame[0],
        'y': vel_localFrame[1],
        'z': vel_localFrame[2]
    })

    rotation_localFrame_msg = roslibpy.Message({
        'x': rot_localFrame[0],
        'y': rot_localFrame[1],
        'z': rot_localFrame[2],
        'w': rot_localFrame[3]
    })

    controlled_entity.SetParam(st.VarType.doubleV3, "LocationMarsFrame", loc_marsFrame)
    controlled_entity.SetParam(st.VarType.doubleV3, "LocationLocalFrame", loc_localFrame)

    try:
        location_marsFrame_publisher.publish(location_marsFrame_msg)
        velocity_marsFrame_publisher.publish(velocity_marsFrame_msg)
        rotation_marsFrame_publisher.publish(rotation_marsFrame_msg)
        location_localFrame_publisher.publish(location_localFrame_msg)
        velocity_localFrame_publisher.publish(velocity_localFrame_msg)
        rotation_localFrame_publisher.publish(rotation_localFrame_msg)
    except Exception as e:
        st.logger_error(f"Error publishing location/rotation to ROS: {str(e)}")


t0: st.timestamp = st.SimGlobals.SimClock.GetTimeNow()

exit_flag = False
while not exit_flag:
    # dt
    t_now: st.timestamp = st.SimGlobals.SimClock.GetTimeNow()
    dt: datetime.timedelta = t_now.as_datetime() - t0.as_datetime()
    dt_sim: float = dt.total_seconds()
    dt_irl: float = 1.0 / st.GetThisSystem().GetParam(st.VarType.double, "LoopFreqHz")

    time.sleep(dt_irl)

    publish_location_and_rotation(dt_sim)

    t0 = t_now

st.leave_sim()
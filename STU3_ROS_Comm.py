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

st.OnScreenLogMessage("ROS_Comm started properly.", "ROS_Comm", st.Severity.Info)

import copy


#################################   Entity and frame setup   #################################
this = st.GetThisSystem()
controlledEntity: st.Entity = this.GetParam(st.VarType.entityRef, "ControlledEntity")

# Reference frames
mars: st.Entity = this.GetParam(st.VarType.entityRef, "MarsReferenceFrame")
marsFrame = mars.GetBodyFixedFrame()
local: st.Entity = this.GetParam(st.VarType.entityRef, "LocalFrame")
localFrame = local.GetBodyFixedFrame()


#################################   Waypoint data setup   #################################
def check_waypoint() -> bool:
    waypoints: list[int] = controlledEntity.GetParamArray(st.VarType.int32, ["Waypoints", "WaypointIDs"])
    visitedWaypoints: list[int] = controlledEntity.GetParamArray(st.VarType.int32, ["Waypoints", "VisitedWaypointIDs"])

    tolerance = 1.5 * controlledEntity.GetParam(st.VarType.double, ["Waypoints", "WaypointVisitTolerance_m"])  # Give it some wiggle room
    roverLoc = controlledEntity.getLocation().WRT_ExprIn(localFrame)
    
    # Invalid before waypoints are initialized
    if len(waypoints) == 0:
        st.OnScreenLogMessage("Warning: there are no waypoints to sample at in this simulation.", 
                              "WaypointSamplingWarning", st.Severity.Warning)
        return False

    closestWaypoint = waypoints[0]
    waypointParamMap = controlledEntity.GetParamMap("Waypoints")
    minDistance = 1e6  # meters
    for i in range(len(waypoints)):
        waypoint = waypoints[i]
        waypointEntity: st.Entity = waypointParamMap.GetParam(st.VarType.entityRef, f"Waypoint{waypoint}")
        waypointLoc = waypointEntity.getLocation().WRT_ExprIn(localFrame)

        distance = np.linalg.norm(waypointLoc - roverLoc)
        if distance < minDistance:
            minDistance = copy.deepcopy(distance)
            closestWaypoint = copy.deepcopy(waypoint)
    
    # Can't get credit for revisiting the same waypoints
    if closestWaypoint in visitedWaypoints:
        st.OnScreenLogMessage("Warning: you tried sampling at a waypoint you already visited.", 
                              "WaypointSamplingWarning", st.Severity.Warning)
        return False
    
    if minDistance <= tolerance:
        visitedWaypoints.append(closestWaypoint)
        controlledEntity.SetParamArray(st.VarType.int32, ["Waypoints", "VisitedWaypointIDs"], visitedWaypoints)
        st.OnScreenLogMessage(f"Success! You're collecting core samples at waypoint #{closestWaypoint}.", 
                              "WaypointSamplingSuccess", st.Severity.Info)
        return True
    else:
        distancePrint = f"Distance to nearest waypoint: {minDistance:.3f} meters, which is greater than the {tolerance:.3f}-meter tolerance."
        st.OnScreenLogMessage("Warning: you tried to sample too far from a waypoint. " + distancePrint, 
                              "WaypointSamplingWarning", st.Severity.Warning)
        return False


#################################   ROS setup   #################################
import roslibpy
st.logger_info("Starting ROS Communication Server...")

try:
    ros = roslibpy.Ros(host='localhost', port=9090)
    ros.run()
except Exception as e:
    st.logger_error(f"Error connecting to ROS: {str(e)}")
    st.OnScreenLogMessage("ROS_Comm failed to connect to ROS. Please restart the sim after ROSBridge is running.", "ROS_Comm", st.Severity.Error)
    
    exit_flag = False
    while not exit_flag:
        # Loop forever just so we don't (sometimes) crash the sim by leaving early
        time.sleep(0.2)
    
    
    st.leave_sim()
    time.sleep(0.5) # Wait a bit so the messages send reliably before the socket closes
    exit(1)
st.logger_info("Connected to ROS")


##############################   Control Services   #################################
# Logger service
Logger_service = roslibpy.Service(ros, '/log_message', 'space_teams_definitions/String')
def handle_logger_request(request, response):
    try:
        log_message = request['data']
        st.OnScreenLogMessage(f"ROS Log: {log_message}", "ROSLog", st.Severity.Info)
        response['success'] = True
        return True
    except Exception as e:
        st.OnScreenLogMessage(f"ROS Log Error: {str(e)}", "ROSLogError", st.Severity.Error)
        response['success'] = False
        return False
Logger_service.advertise(handle_logger_request)


# Steer_service
steer_service = roslibpy.Service(ros, '/Steer', 'space_teams_definitions/Float')
def handle_steer_request(request, response):
    try:
        data = request['data']
        if controlledEntity.GetParam(st.VarType.bool, "IsActive") == True:
            controlledEntity.SetParam(st.VarType.double, ["ControlCmd", "SteerRight"], data)
            if not controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"]):
                controlledEntity.SetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"], True)
        
        response['success'] = True
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling Steer request: {str(e)}")
        response['success'] = False
        return False
steer_service.advertise(handle_steer_request)


# Accelerator service
Accelerator_service = roslibpy.Service(ros, '/Accelerator', 'space_teams_definitions/Float')
def handle_accelerator_request(request, response):
    try:
        accel_value = request['data']
        if controlledEntity.GetParam(st.VarType.bool, "IsActive") == True:
            controlledEntity.SetParam(st.VarType.double, ["ControlCmd", "Accelerator"], accel_value)
            if not controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"]):
                controlledEntity.SetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"], True)
        
        response['success'] = True
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling Accelerator request: {str(e)}")
        response['success'] = False
        return False
Accelerator_service.advertise(handle_accelerator_request)


# Reverse service
Reverse_service = roslibpy.Service(ros, '/Reverse', 'space_teams_definitions/Float')
def handle_reverse_request(request, response):
    try:
        reverse_value = request['data']
        if controlledEntity.GetParam(st.VarType.bool, "IsActive") == True:
            controlledEntity.SetParam(st.VarType.double, ["ControlCmd", "Brake"], reverse_value)
            if not controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"]):
                controlledEntity.SetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"], True)
        
        response['success'] = True
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling Reverse request: {str(e)}")
        response['success'] = False
        return False
Reverse_service.advertise(handle_reverse_request)


# Brake service
Brake_service = roslibpy.Service(ros, '/Brake', 'space_teams_definitions/Float')
def handle_brake_request(request, response):
    try:
        brake_value = request['data']
        if controlledEntity.GetParam(st.VarType.bool, "IsActive") == True:
            controlledEntity.SetParam(st.VarType.bool, ["ControlCmd", "Handbrake"], brake_value > 0.5)
            if not controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"]):
                controlledEntity.SetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"], True)
        
        response['success'] = True
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling Brake request: {str(e)}")
        response['success'] = False
        return False
Brake_service.advertise(handle_brake_request)


# CoreSample service
CoreSample_service = roslibpy.Service(ros, '/CoreSample', 'space_teams_definitions/Float')
def handle_core_sample_request(request, response):
    try:
        validSampling = check_waypoint()
        validControlledEntity = controlledEntity.GetParam(st.VarType.bool, "IsActive") == True
        if validSampling and validControlledEntity:
            beginTimeWarpPayload: st.ParamMap = st.ParamMap()
            beginTimeWarpPayload.AddParam(st.VarType.entityRef, "Rover", controlledEntity)
            st.SimGlobals.DispatchEvent("BeginTimeWarp", beginTimeWarpPayload)
            if not controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"]):
                controlledEntity.SetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"], True)

        response['success'] = True
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling CoreSample request: {str(e)}")
        response['success'] = False
        return False
CoreSample_service.advertise(handle_core_sample_request)

# CoreSamplingComplete publisher
coreSamplingComplete_publisher = roslibpy.Topic(ros, '/CoreSamplingComplete', 'geometry_msgs/Point')
def publish_coreSamplingComplete(payload: st.ParamMap, time: st.timestamp):
    # Junk message that has no actual meaning; just need the event itself:
    coreSamplingComplete_msg = roslibpy.Message({'x': 0.0, 'y': 0.0, 'z': 0.0})

    try:
        coreSamplingComplete_publisher.publish(coreSamplingComplete_msg)
    except Exception as e:
        st.logger_fatal(f"Error publishing CoreSamplingComplete to ROS: {str(e)}")

st.SimGlobals.AddEventListener("EndTimeWarp", publish_coreSamplingComplete)


####################################   Camera Control Services   #################################'
# get camera entity
camera: st.Entity = st.GetThisSystem().GetParam(st.VarType.entityRef, "Camera")

# NOTE: FOV CHANGING DISABLED; WOULD REQUIRE REPLACEMENT CameraInfo IN ROS
# # change FOV service
# minimum_fov = 40.0
# maximum_fov = 90.0

# ChangeFOV_service = roslibpy.Service(ros, '/ChangeFOV', 'space_teams_definitions/Float')
# def handle_change_fov_request(request, response):
#     try:
#         fov_value = request['data']
#         clamped_fov = max(minimum_fov, min(fov_value, maximum_fov))
#         camera.SetParam(st.VarType.double, "FOV", clamped_fov)
        
#         response['success'] = True

#         st.logger_info(f"Camera FOV set to {camera.GetParam(st.VarType.double, 'FOV')}")
#         return True
#     except Exception as e:
#         st.logger_error(f"Error handling ChangeFOV request: {str(e)}")
#         response['success'] = False
#         return False
#     finally:
#         pass
# ChangeFOV_service.advertise(handle_change_fov_request)

# change Exposure service
minimum_exposure = 5.0
maximum_exposure = 20.0
ChangeExposure_service = roslibpy.Service(ros, '/ChangeExposure', 'space_teams_definitions/Float')
def handle_change_exposure_request(request, response):
    try:
        exposure_value = request['data']
        clamped_exposure = max(minimum_exposure, min(exposure_value, maximum_exposure))
        camera.SetParam(st.VarType.double, "Exposure", clamped_exposure)
        
        response['success'] = True

        st.logger_info(f"Camera exposure set to {camera.GetParam(st.VarType.double, 'Exposure')}")
        return True
    except Exception as e:
        st.logger_fatal(f"Error handling ChangeExposure request: {str(e)}")
        response['success'] = False
        return False

ChangeExposure_service.advertise(handle_change_exposure_request)

exit_flag = False
while not exit_flag:
    time.sleep(1.0 / st.GetThisSystem().GetParam(st.VarType.double, "LoopFreqHz"))

st.leave_sim()
time.sleep(0.5) # Wait a bit so the messages send reliably before the socket closes
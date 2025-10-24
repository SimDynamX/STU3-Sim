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
# Now, when below the boilerplate section, you can import more things

st.OnScreenLogMessage("EventHandler started properly.", "EventHandler", st.Severity.Info)

import copy
from enum import Enum


class TimeParams:
    def __init__(self, multiplier: float, maxTimeScale: float):
        self.multiplier: float = multiplier
        self.maxTimeScale: float = maxTimeScale


class WeatherParams:
    hour = 3600.0
    day = 86400.0

    stormStartTime_0 = 1.0 * day
    stormStartTime_1 = stormStartTime_0 + 2.0 * hour
    stormEndTime_0 = stormStartTime_1 + 1.0 * day
    stormEndTime_1 = stormEndTime_0 + 4.0 * hour


class AtmoParams:
    class Sub_100nm_Diam_Gas:
        nominal_ScaleHeight_km = 11.1
        nominal_MaxDensity_kmol_m3 = 461.467e-6
        
        storm_ScaleHeight_km = 11.1
        storm_MaxDensity_kmol_m3 = 461.467e-6
    
    class Over_100nm_Diam_Particulate:
        nominal_ScaleHeight_km = 11.1
        nominal_MaxDensity_kmol_m3 = 0.02
        nominal_RGB_Scatter_Magnitude = np.array([1.0, 0.83, 0.68])
        nominal_RGB_Absorb_Magnitude = np.array([0.13, 0.52, 1.0])
        nominal_Absorb_Strength_1_km = 0.005

        storm_ScaleHeight_km = 11.1
        storm_MaxDensity_kmol_m3 = 0.1
        storm_RGB_Scatter_Magnitude = np.array([1.0, 0.83, 0.68])
        storm_RGB_Absorb_Magnitude = np.array([0.13, 0.52, 1.0])
        storm_Absorb_Strength_1_km = 0.2


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolate on the scale given by a to b, using t as the point on that scale.
    Examples
    --------
        50 == lerp(0, 100, 0.5)
        4.2 == lerp(1, 5, 0.8)
    """
    return (1 - t) * a + t * b


def inv_lerp(a: float, b: float, v: float) -> float:
    """Inverse Linar Interpolation, get the fraction between a and b on which v resides.
    Examples
    --------
        0.5 == inv_lerp(0, 100, 50)
        0.8 == inv_lerp(1, 5, 4.2)
    """
    return (v - a) / (b - a)


def remap(i_min: float, i_max: float, o_min: float, o_max: float, v: float) -> float:
    """Remap values from one linear scale to another, a combination of lerp and inv_lerp.
    i_min and i_max are the scale on which the original value resides,
    o_min and o_max are the scale to which it should be mapped.
    Examples
    --------
        45 == remap(0, 100, 40, 50, 50)
        6.2 == remap(1, 5, 3, 7, 4.2)
    """
    return lerp(o_min, o_max, inv_lerp(i_min, i_max, v))


def IsAtWaypoint(controlledEntity: st.Entity) -> bool:
    return controlledEntity.GetParam(st.VarType.bool, ["State", "IsAtWaypoint"])


def ToggleIsAtWaypoint(controlledEntity: st.Entity, isApproaching: bool):
    controlledEntity.SetParam(st.VarType.bool, ["State", "IsAtWaypoint"], isApproaching)


def GetElapsedTimeWarpTime(controlledEntity: st.Entity) -> float:
    return controlledEntity.GetParam(st.VarType.double, ["State", "ElapsedTimeWarpTime"])


def SetElapsedTimeWarpTime(controlledEntity: st.Entity, newElapsedTimeWarpTime: float):
    controlledEntity.SetParam(st.VarType.double, ["State", "ElapsedTimeWarpTime"], newElapsedTimeWarpTime)


def AnimTime(controlledEntity: st.Entity, timeParams: TimeParams):
    # Get the timescale
    timeScale: float = st.SimGlobals.SimClock.GetTimescale()
    phase: str = controlledEntity.GetParam(st.VarType.string, ["State", "TimeWarpPhase"])
    
    # Modify the timescale based on the phase
    if phase == "RampUp":
        timeScale = min(timeScale * timeParams.multiplier, timeParams.maxTimeScale)
        if timeScale == timeParams.maxTimeScale:
            phase = "Plateau"
    elif phase == "Plateau":
        elapsedTimeWarpTime: float = GetElapsedTimeWarpTime(controlledEntity)
        targetTimeWarpTime: float = controlledEntity.GetParam(st.VarType.double, ["State", "TargetTimeWarpTime"])
        if elapsedTimeWarpTime >= targetTimeWarpTime:
            phase = "RampDown"
    elif phase == "RampDown":
        timeScale = max(timeScale / timeParams.multiplier, 1.0)
        if timeScale == 1.0:
            endTimeWarpPayload: st.ParamMap = st.ParamMap()
            st.SimGlobals.DispatchEvent("EndTimeWarp", endTimeWarpPayload)
    
    # Set the new timescale
    st.SimGlobals.SimClock.SetTimescale(timeScale)
    controlledEntity.SetParam(st.VarType.string, ["State", "TimeWarpPhase"], phase)


def GetWaypointNum(controlledEntity: st.Entity) -> int:
    return controlledEntity.GetParam(st.VarType.int32, ["State", "WaypointNum"])


def IncrementWaypoint(controlledEntity: st.Entity):
    newWaypointNum: int = GetWaypointNum(controlledEntity) + 1
    controlledEntity.SetParam(st.VarType.int32, ["State", "WaypointNum"], newWaypointNum)


this = st.GetThisSystem()
mars: st.Entity = this.GetParam(st.VarType.entityRef, "Mars")
thirdPersonPawn: st.Entity = this.GetParam(st.VarType.entityRef, "ThirdPersonPawn")
drivingPawn: st.Entity = this.GetParam(st.VarType.entityRef, "DrivingPawn")
controlledEntity: st.Entity = this.GetParam(st.VarType.entityRef, "ControlledEntity")

multiplier: float = this.GetParam(st.VarType.double, "Multiplier")
maxTimeScale: float = this.GetParam(st.VarType.double, "MaxTimeScale")
timeParams: TimeParams = TimeParams(multiplier, maxTimeScale)

numWaypoints: int = this.GetParam(st.VarType.int32, "NumWaypoints")


def Response_BeginTimeWarp(payload: st.ParamMap, time: st.timestamp):
    ToggleIsAtWaypoint(controlledEntity, True)
    st.OnScreenAlert("Beginning core sampling; all commands disabled.", "Timewarp", st.Severity.Warning)
    controlledEntity.SetParam(st.VarType.string, ["State", "TimeWarpPhase"], "RampUp")


def Response_EndTimeWarp(payload: st.ParamMap, time: st.timestamp):
    st.SimGlobals.SimClock.SetTimescale(1.0)  # Just in case
    st.OnScreenAlert("Core sampling complete; all commands re-enabled.", "Timewarp", st.Severity.Warning)
    ToggleIsAtWaypoint(controlledEntity, False)
    SetElapsedTimeWarpTime(controlledEntity, 0.0)  # Reset for next waypoint
    IncrementWaypoint(controlledEntity)

    elapsedDrivingTime_str = controlledEntity.GetParam(st.VarType.string, ["Score", "ElapsedDrivingTime"])
    controlledEntity.SetParam(st.VarType.string, ["Score", "TimeAtLastWaypoint"], elapsedDrivingTime_str)


def Response_STU3_RoverFlipped(payload: st.ParamMap, time: st.timestamp, ):
    st.OnScreenAlert("Game over! Your rover flipped.", "STU3", st.Severity.Error)
        
    timeAtLastWaypoint_str = controlledEntity.GetParam(st.VarType.string, ["Score", "TimeAtLastWaypoint"])
    waypointsReached_str = controlledEntity.GetParam(st.VarType.string, ["Score", "WaypointsReached"])

    st.OnScreenLogMessage("Final time:                  " + timeAtLastWaypoint_str, "Time", st.Severity.Info)
    st.OnScreenLogMessage("Number of waypoints reached: " + waypointsReached_str, "Waypoints", st.Severity.Info)
    controlledEntity.SetParam(st.VarType.bool, "IsActive", False)


def Wait(seconds: float):
    time.sleep(seconds)


def UpdateWeather(elapsedTotalSimTime: float):
    atmoMap = mars.GetParamMap(["#Planet", "Atmosphere"])

    stormStartTime_0 = WeatherParams.stormStartTime_0
    stormStartTime_1 = WeatherParams.stormStartTime_1
    stormEndTime_0 = WeatherParams.stormEndTime_0
    stormEndTime_1 = WeatherParams.stormEndTime_1

    nominal_MaxDensity_kmol_m3 = AtmoParams.Over_100nm_Diam_Particulate.nominal_MaxDensity_kmol_m3
    storm_MaxDensity_kmol_m3 = AtmoParams.Over_100nm_Diam_Particulate.storm_MaxDensity_kmol_m3

    nominal_Absorb_Strength_1_km = AtmoParams.Over_100nm_Diam_Particulate.nominal_Absorb_Strength_1_km
    storm_Absorb_Strength_1_km = AtmoParams.Over_100nm_Diam_Particulate.storm_Absorb_Strength_1_km

    # Fade in
    if stormStartTime_1 >= elapsedTotalSimTime > stormStartTime_0:
        MaxDensity_kmol_m3 = remap(stormStartTime_0, stormStartTime_1, nominal_MaxDensity_kmol_m3, 
                                   storm_MaxDensity_kmol_m3, elapsedTotalSimTime)
        Absorb_Strength_1_km = remap(stormStartTime_0, stormStartTime_1, nominal_Absorb_Strength_1_km, 
                                     storm_Absorb_Strength_1_km, elapsedTotalSimTime)
        atmoMap.SetParam(st.VarType.double, ["Over_100nm_Diam_Particulate", "MaxDensity_kmol_m3"], MaxDensity_kmol_m3)
        atmoMap.SetParam(st.VarType.double, ["Over_100nm_Diam_Particulate", "Absorb_Strength_1_km"], Absorb_Strength_1_km)
    
    # Fade out
    elif stormEndTime_1 >= elapsedTotalSimTime > stormEndTime_0:
        MaxDensity_kmol_m3 = remap(stormEndTime_0, stormEndTime_1, storm_MaxDensity_kmol_m3, 
                                   nominal_MaxDensity_kmol_m3, elapsedTotalSimTime)
        Absorb_Strength_1_km = remap(stormEndTime_0, stormEndTime_1, storm_Absorb_Strength_1_km, 
                                     nominal_Absorb_Strength_1_km, elapsedTotalSimTime)
        atmoMap.SetParam(st.VarType.double, ["Over_100nm_Diam_Particulate", "MaxDensity_kmol_m3"], MaxDensity_kmol_m3)
        atmoMap.SetParam(st.VarType.double, ["Over_100nm_Diam_Particulate", "Absorb_Strength_1_km"], Absorb_Strength_1_km)


st.SimGlobals.AddEventListener("BeginTimeWarp", Response_BeginTimeWarp)
st.SimGlobals.AddEventListener("EndTimeWarp", Response_EndTimeWarp)
st.SimGlobals.AddEventListener("STU3_RoverFlipped", Response_STU3_RoverFlipped)

t0: st.timestamp = st.SimGlobals.SimClock.GetTimeNow()

elapsedTotalTime: float = 0.0
elapsedDrivingTime: float = 0.0

drivingTimeLimit_s: float = controlledEntity.GetParam(st.VarType.double, ["Score", "DrivingTimeLimit_s"])

exit_flag = False
while not exit_flag:
    printOnTick: bool = this.GetParam(st.VarType.bool, "PrintOnTick")
    
    hasReceivedFirstROSCommand: bool = controlledEntity.GetParam(st.VarType.bool, ["State", "HasReceivedFirstROSCommand"])

    # dt
    t_now: st.timestamp = st.SimGlobals.SimClock.GetTimeNow()
    dt: datetime.timedelta = t_now.as_datetime() - t0.as_datetime()
    dt_sim: float = dt.total_seconds()
    dt_irl: float = 1.0 / st.GetThisSystem().GetParam(st.VarType.double, "LoopFreqHz")

    elapsedTotalTime += dt_sim

    # Update weather on Mars
    UpdateWeather(elapsedTotalTime)

    # If we've gone to enough waypoints, end the sim and print the score
    currentNumWaypoints: int = GetWaypointNum(controlledEntity)
    if currentNumWaypoints >= numWaypoints:
        exit_flag = True
        timeAtLastWaypoint_str = controlledEntity.GetParam(st.VarType.string, ["Score", "TimeAtLastWaypoint"])
        st.OnScreenAlert("Congratulations, you completed the mission! Final time: " + timeAtLastWaypoint_str, "Finished", st.Severity.Info)
    
    if controlledEntity.GetParam(st.VarType.bool, "IsActive") == False:
        exit_flag = True

    # If doing a waypoint animation, ramp up and down the timescale accordingly
    if IsAtWaypoint(controlledEntity):
        elapsedTimeWarpTime = GetElapsedTimeWarpTime(controlledEntity)
        elapsedTimeWarpTime += dt_sim
        SetElapsedTimeWarpTime(controlledEntity, elapsedTimeWarpTime)
        AnimTime(controlledEntity, timeParams)
    # Else, add to the total elapsed driving time
    else:
        if hasReceivedFirstROSCommand:
            elapsedDrivingTime += dt_sim
    
    if printOnTick:
        st.OnScreenAlert("Elapsed driving time: " + str(round(elapsedDrivingTime / 60.0, 2)) + 
                        " minutes", "ElapsedDrivingTime", st.Severity.Info)
    
    if elapsedDrivingTime >= drivingTimeLimit_s:
        st.OnScreenAlert("Maximum driving time of 1 hour exceeded; stopping simulation.", "TimeLimit", st.Severity.Error)
        
        timeAtLastWaypoint_str = controlledEntity.GetParam(st.VarType.string, ["Score", "TimeAtLastWaypoint"])
        waypointsReached_str = controlledEntity.GetParam(st.VarType.string, ["Score", "WaypointsReached"])

        st.OnScreenLogMessage("Final time:                  " + timeAtLastWaypoint_str, "Time", st.Severity.Info)
        st.OnScreenLogMessage("Number of waypoints reached: " + waypointsReached_str, "Waypoints", st.Severity.Info)
        controlledEntity.SetParam(st.VarType.bool, "IsActive", False)
    
    # Update scoring params
    elapsedTime = str(datetime.timedelta(seconds=round(elapsedDrivingTime)))
    waypointsReached = f"{currentNumWaypoints} / {numWaypoints}"
    controlledEntity.SetParam(st.VarType.string, ["Score", "ElapsedDrivingTime"], elapsedTime)
    controlledEntity.SetParam(st.VarType.string, ["Score", "WaypointsReached"], waypointsReached)

    # Get copies of rover commands
    accelCommand = f'{controlledEntity.GetParam(st.VarType.double, ["ControlCmd", "Accelerator"]):.3f}'
    steerCommand = f'{controlledEntity.GetParam(st.VarType.double, ["ControlCmd", "SteerRight"]):.3f}'
    reverseCommand = f'{controlledEntity.GetParam(st.VarType.double, ["ControlCmd", "Brake"]):.3f}'
    brakeCommand = f'{controlledEntity.GetParam(st.VarType.bool, ["ControlCmd", "Handbrake"]):.3f}'
    
    # Set display params on all pawns
    thirdPersonPawnParams = thirdPersonPawn.GetParamMap(["#Pawn", "Gadgets", "2", "Params"])
    thirdPersonPawnParams.SetParam(st.VarType.string, "ElapsedDrivingTime", elapsedTime)
    thirdPersonPawnParams.SetParam(st.VarType.string, "WaypointsReached", waypointsReached)
    thirdPersonPawnParams.SetParam(st.VarType.string, "AccelerationCommand", accelCommand)
    thirdPersonPawnParams.SetParam(st.VarType.string, "SteeringCommand", steerCommand)
    thirdPersonPawnParams.SetParam(st.VarType.string, "ReverseCommand", reverseCommand)
    thirdPersonPawnParams.SetParam(st.VarType.string, "BrakingCommand", brakeCommand)

    drivingPawnParams = drivingPawn.GetParamMap(["#Pawn", "Gadgets", "2", "Params"])
    drivingPawnParams.SetParam(st.VarType.string, "ElapsedDrivingTime", elapsedTime)
    drivingPawnParams.SetParam(st.VarType.string, "WaypointsReached", waypointsReached)
    drivingPawnParams.SetParam(st.VarType.string, "AccelerationCommand", accelCommand)
    drivingPawnParams.SetParam(st.VarType.string, "SteeringCommand", steerCommand)
    drivingPawnParams.SetParam(st.VarType.string, "ReverseCommand", reverseCommand)
    drivingPawnParams.SetParam(st.VarType.string, "BrakingCommand", brakeCommand)

    t0 = t_now
    time.sleep(dt_irl)

exit_flag = False
while not exit_flag:
    # Loop forever just so we don't (sometimes) crash the sim by leaving early
    time.sleep(0.2)

st.leave_sim()
time.sleep(0.5) # Wait a bit so the messages send reliably before the socket closes
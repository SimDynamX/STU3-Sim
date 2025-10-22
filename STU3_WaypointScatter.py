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

st.OnScreenLogMessage("WaypointScatter started properly.", "WaypointScatter", st.Severity.Info)

import random


this = st.GetThisSystem()
controlledEntity: st.Entity = this.GetParam(st.VarType.entityRef, "ControlledEntity")

# Planet data
planetData = st.ProcPlanet.DataStore()
planetRadius = this.GetParam(st.VarType.double, "Radius")

# Local frame
localFrame_en: st.Entity = this.GetParam(st.VarType.entityRef, "LocalFrame")
localFrame = localFrame_en.GetBodyFixedFrame()

# Datasets
planetDataPath = "../SharedData/PlanetData/"
datasets = this.GetParamArray(st.VarType.string, "Datasets")
datasetPriorities = this.GetParamArray(st.VarType.double, "DatasetPriorities")

for i in range(len(datasets)):
    planetData.AddGeoBinAltimetryLayer(datasetPriorities[i], planetDataPath + datasets[i], st.ProcPlanet.GeoBin_Extra_Args())


def AddParamOps(en: st.ParamMap):
    pass


def RandomVector3(radius: float) -> np.ndarray[float]:
    normalized = np.array([random.random(), random.random(), random.random()])
    vec: np.ndarray[float] = radius * 2.0 * (normalized - 0.5)
    return vec


def PlaceWaypoint(id: int, loc: np.ndarray[float], rotSnapped: np.ndarray[float], planetFrame: st.frames.Frame):
    # Spawn the waypoint
    path: str = "Core/SharedData/SCAssets/Basic/Waypoint.enconf"
    name: str = "Waypoint" + str(id)
    systems: list[str] = []
    waypoint: st.Entity = st.SimGlobals.AddEntityFromConfig(path, name, systems, AddParamOps)
    
    # Set waypoint location
    waypoint.setResidentFrame(planetFrame)
    zero = np.zeros(3)
    waypoint.setLocVelAcc(st.frames.FramedLocVelAcc(st.frames.rva_struct(loc, zero, zero), planetFrame), planetFrame)
    waypoint.setRotation_Quat(rotSnapped, planetFrame)

    visibilityGlobal: bool = this.GetParam(st.VarType.bool, "Visibility")
    allVisible: bool = this.GetParam(st.VarType.bool, "AllVisible")
    visibleIndices: list[int] = this.GetParamArray(st.VarType.int32, "VisibleIndices")
    
    visibilityCondition = visibilityGlobal and (id in visibleIndices or allVisible)
    waypoint.SetParam(st.VarType.double, ["Graphics", "Scale"], 10.0 if visibilityCondition else 0.0)

    # Add to array (hopefully this doesn't memory leak or crash anymore?)
    controlledEntity.AddParam(st.VarType.entityRef, ["Waypoints", f"Waypoint{id}"], waypoint)
    waypointIDs: list[int] = controlledEntity.GetParamArray(st.VarType.int32, ["Waypoints", "WaypointIDs"])
    waypointIDs.append(id)
    controlledEntity.SetParamArray(st.VarType.int32, ["Waypoints", "WaypointIDs"], waypointIDs)


def WaypointLocations(seed: int, num: int, scatterCenter: np.ndarray[float], radiusFromCenter: float):
    # Set seed
    random.seed(seed)
    
    # Planet parameters
    planet: st.Entity = this.GetParam(st.VarType.entityRef, "Planet")
    planetFrame: st.frames.Frame = planet.GetBodyFixedFrame()

    # Local North-West-Up frame
    nwu = st.PlanetUtils.NorthWestUpFromLocation(scatterCenter, planetRadius)
    
    # Scattering
    scatterFraction: float = this.GetParam(st.VarType.double, "ScatterFraction")
    minRadius: float = radiusFromCenter * (1 - scatterFraction)
    maxRadius: float = radiusFromCenter * (1 + scatterFraction)

    for i in range(num):
        # Set waypoint location
        angle: float = 2.0 * np.pi * random.random()
        radius = minRadius + (maxRadius - minRadius) * random.random()
        loc = scatterCenter + radius * (nwu.north() * np.cos(angle) + nwu.west() * np.sin(angle))
        
        # Snap waypoint to surface
        locSnapped, surfaceNormal = st.ProcPlanet.SampleGround(planetData, loc, planetRadius, 0.5, 22) 
        forward = st.PlanetUtils.ForwardLeftUpFromAzimuth(locSnapped, 0.0, planetRadius).forward()
        rotSnapped = st.ProcPlanet.AlignToGround(surfaceNormal, forward)

        # Print location
        locSnapped_wrtLocal = st.frames.FramedLoc(locSnapped, planetFrame).WRT_ExprIn(localFrame)
        st.logger_info("Location of waypoint " + str(i).zfill(3) + " in the Mars frame:  " + str(locSnapped))
        st.logger_info("Location of waypoint " + str(i).zfill(3) + " in the local frame: " + str(locSnapped_wrtLocal) + "\n")

        # Place waypoint
        PlaceWaypoint(i, locSnapped, rotSnapped, planetFrame)


# Get params
seed: int = this.GetParam(st.VarType.int32, "Seed")
numWaypoints: int = this.GetParam(st.VarType.int32, "NumWaypoints")
scatterCenter: np.ndarray[float] = this.GetParam(st.VarType.doubleV3, "WaypointScatterCenter")
radiusFromCenter: float = this.GetParam(st.VarType.double, "WaypointScatterRadius")

# Spawn waypoints
WaypointLocations(seed, numWaypoints, scatterCenter, radiusFromCenter)


# exit_flag = False
# while not exit_flag:
#     # Loop forever just so we don't crash the sim by leaving early
#     dt_irl: float = 1.0 / st.GetThisSystem().GetParam(st.VarType.double, "LoopFreqHz")
#     time.sleep(dt_irl)

st.leave_sim()
time.sleep(5.0) # Wait a bit so the messages send reliably before the socket closes

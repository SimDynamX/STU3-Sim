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

st.OnScreenLogMessage("ImageSender started properly.", "ImageSender", st.Severity.Info)

import zmq
import cv2
import numpy as np

import time
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
import json
from PIL import Image
from typing import Any


#############################
# Camera image publisher using ZMQ and OpenCV
####################
@dataclass
class CameraConfig:
    width: int = 640
    height: int = 480

DEBUG_IMG_FPS = 30.0


def _wait_for_subscriber(pub_socket: zmq.Socket, timeout_s: float = 2.0) -> bool:
    """
    Robust, bounded wait for a TCP peer to connect to the PUB socket.
    Uses a monitor + poller with a hard wall-clock timeout.
    Returns True if we saw EVENT_ACCEPTED, else False after timeout.
    Set env ST_ZMQ_NOWAIT=1 to skip waiting entirely.
    """
    try:
        if os.getenv("ST_ZMQ_NOWAIT") == "1" or timeout_s <= 0:
            return False

        mon_addr = "inproc://pub_mon"
        # Listen for ACCEPTED (peer connected) plus a few harmless extras
        pub_socket.monitor(mon_addr,
                           zmq.EVENT_ACCEPTED | zmq.EVENT_LISTENING | zmq.EVENT_CONNECT_DELAYED)
        mon = pub_socket.get_monitor_socket()

        # Use a poller instead of relying solely on RCVTIMEO
        poller = zmq.Poller()
        poller.register(mon, zmq.POLLIN)

        deadline = time.time() + timeout_s
        accepted = False

        while time.time() < deadline:
            # Poll in short slices so KeyboardInterrupt is responsive
            remaining_ms = max(1, int((deadline - time.time()) * 1000))
            events = dict(poller.poll(min(remaining_ms, 100)))
            if events.get(mon) == zmq.POLLIN:
                try:
                    frames = mon.recv_multipart(zmq.NOBLOCK)
                except zmq.Again:
                    continue
                if not frames:
                    continue
                # First frame encodes event id and value; event id is the first 2 bytes (uint16 LE)
                raw = frames[0]
                if len(raw) >= 2:
                    event_id = int.from_bytes(raw[:2], "little")
                    if event_id == zmq.EVENT_ACCEPTED:
                        accepted = True
                        break
            # loop until deadline

        return accepted

    except Exception as e:
        # If anything goes weird with monitors, just don't block startup
        try:
            st.logger_warn(f"_wait_for_subscriber: monitor fallback due to: {e}")
        except Exception:
            pass
        return False
    finally:
        # Clean up the monitor if it was enabled
        try:
            mon.close(0)
        except Exception:
            pass
        try:
            pub_socket.disable_monitor()
        except Exception:
            pass


class ImagePublisher:
    def __init__(self, host: str = "0.0.0.0", port: int = 55556):
        """Initialize the image publisher with configurable host and port.

        Args:
            host (str): Host address to bind to
            port (int): Port number to use
        """
        self.context = zmq.Context()
        self.socket = self._setup_socket(host, port)
        
        # Store camera configurations
        self.rgb_config = None
        self.depth_config = None
        
        # Timing and stats
        self.last_time = time.time()
        self.frames_count = 0
        self.frame_count = 0  # Used for generating dynamic patterns

    def _setup_socket(self, host: str, port: int) -> zmq.Socket:
        """Setup and configure the ZMQ socket with optimal settings."""
        self.context.setsockopt(zmq.MAX_SOCKETS, 1)
        socket_ = self.context.socket(zmq.PUB)

        # Configure socket for high-throughput streaming
        socket_.setsockopt(zmq.SNDHWM, 2)   # small HWM + CONFLATE => latest only
        socket_.setsockopt(zmq.RCVHWM, 2)
        socket_.setsockopt(zmq.LINGER, 0)
        socket_.setsockopt(zmq.CONFLATE, 1)  # Only keep latest message
        socket_.setsockopt(zmq.SNDBUF, 2*1024*1024)
        socket_.setsockopt(zmq.TCP_KEEPALIVE, 1)
        socket_.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 120)
        socket_.setsockopt(zmq.IMMEDIATE, 1)  # don't queue if no peer

        endpoint = f"tcp://{host}:{port}"
        socket_.bind(endpoint)
        st.logger_info(f"Publisher bound to {endpoint}")

        # ---> Key addition: wait briefly for a TCP accept, then small grace
        # if _wait_for_subscriber(socket_, timeout_s=2.0):
        #     st.logger_info("Subscriber connected (TCP). Waiting 200ms for SUBSCRIBE to apply...")
        #     time.sleep(0.2)
        # else:
        #     st.logger_info("No subscriber detected within timeout; publishing anyway (early msgs may be dropped).")

        return socket_


    def setup_rgb_camera(self, config: CameraConfig = CameraConfig()) -> bool:
        """Setup RGB camera configuration.

        Args:
            config (CameraConfig): Camera configuration parameters

        Returns:
            bool: True if setup was successful
        """
        self.rgb_config = config
        st.logger_info(f"RGB camera configured for {config.width}x{config.height} @ {DEBUG_IMG_FPS} DEBUG_IMG_FPS")
        return True

    def setup_depth_camera(self, config: CameraConfig = CameraConfig()) -> bool:
        """Setup depth camera configuration.

        Args:
            config (CameraConfig): Camera configuration parameters

        Returns:
            bool: True if setup was successful
        """
        self.depth_config = config
        st.logger_info(f"Depth camera configured for {config.width}x{config.height} @ {DEBUG_IMG_FPS} DEBUG_IMG_FPS")
        return True

    def _generate_rgb_frame(self) -> np.ndarray:
        """Generate a dummy RGB frame with a moving pattern."""
        if not self.rgb_config:
            return None
            
        # Create a moving color pattern
        x = np.linspace(0, 2*np.pi, self.rgb_config.width)
        y = np.linspace(0, 2*np.pi, self.rgb_config.height)
        X, Y = np.meshgrid(x, y)
        
        # Create moving waves for each color channel
        t = self.frame_count * 0.1
        r = np.sin(X + t) * 128 + 128
        g = np.sin(Y - t) * 128 + 128
        b = np.sin(X + Y + t) * 128 + 128
        
        # Combine channels and ensure uint8 format
        frame = np.stack([b, g, r], axis=2).astype(np.uint8)
        return frame

    def _generate_depth_frame(self) -> np.ndarray:
        """Generate a dummy depth frame with a moving pattern."""
        if not self.depth_config:
            return None
            
        # Create a moving depth pattern (single channel)
        x = np.linspace(0, 2*np.pi, self.depth_config.width)
        y = np.linspace(0, 2*np.pi, self.depth_config.height)
        X, Y = np.meshgrid(x, y)
        
        t = self.frame_count * 0.05
        # Create a circular wave pattern
        center_x = self.depth_config.width / 2
        center_y = self.depth_config.height / 2
        R = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        depth = (np.sin(R * 0.1 - t) * 128 + 128).astype(np.uint8)
        
        # Convert to 3-channel format (all channels identical for grayscale)
        frame = np.stack([depth, depth, depth], axis=2)
        return frame

    def _send_frame(self, frame: np.ndarray, frame_type: str) -> None:
        """Send a frame with header indicating frame type and dimensions."""
        try:
            frame_time = time.time()
            # Convert frame to contiguous array for faster tobytes()
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)
            img_data = frame.tobytes()
            
            header = "ERROR_HEADER"
            if frame_type == "RGB":
                # Header format: TYPE#HEIGHT#WIDTH#CHANNELS#
                header = f"{frame_type}#{frame.shape[0]:04d}#{frame.shape[1]:04d}#{frame.shape[2]:04d}#"
            elif frame_type == "DEPTH":
                header = f"{frame_type}#{frame.shape[0]:04d}#{frame.shape[1]:04d}#1#"
            else:
                st.logger_error(f"Unknown frame type: {frame_type}")
                raise Exception(f"Unknown frame type: {frame_type}")
            
            message = header.encode('ascii') + img_data
            
            # Send as a single message
            self.socket.send(message, flags=zmq.NOBLOCK)
            # st.logger_info(f"Sent {frame_type} frame of size {len(message)} bytes")
            
            # Update statistics
            self.frames_count += 1
            current_time = time.time()
            if current_time - self.last_time > 1.0:
                fps = self.frames_count / (current_time - self.last_time)
                encode_time = (time.time() - frame_time) * 1000
                st.logger_info(f"{frame_type}: {fps:.1f} FPS, Encode+Send: {encode_time:.1f}ms")
                self.frames_count = 0
                self.last_time = current_time
                
        except zmq.Again:
            st.logger_warn(f"Send buffer full, skipping {frame_type} frame")

    def publish_RGB_frame(self, frame: np.ndarray) -> None:
        """Publish a single RGB frame."""
        self._send_frame(frame, "RGB")

    
    def publish_Depth_frame(self, frame: np.ndarray) -> None:
        """Publish a single Depth frame."""
        self._send_frame(frame, "DEPTH")

    # Debug function to publish test frames
    def publish_test_frames(self) -> None:
        """Publish frames from simulated cameras."""
        try:
            target_interval = 1.0 / DEBUG_IMG_FPS
            next_frame_time = time.time()
            
            while True:
                current_time = time.time()
                if current_time < next_frame_time:
                    # Use a shorter sleep to be more responsive
                    time.sleep(min(0.001, next_frame_time - current_time))
                    continue
                
                self.frame_count += 1
                
                # Pre-generate frames to reduce latency between sends
                rgb_frame = self._generate_rgb_frame() if self.rgb_config else None
                depth_frame = self._generate_depth_frame() if self.depth_config else None
                
                # Send frames as close together as possible
                if rgb_frame is not None:
                    self._send_frame(rgb_frame, "RGB")
                if depth_frame is not None:
                    self._send_frame(depth_frame, "DEPTH")
                
                # Calculate next frame time based on target rate
                next_frame_time = current_time + target_interval

        except KeyboardInterrupt:
            st.logger_info("Shutting down...")
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Release resources and close connections."""
        self.socket.close()
        self.context.term()

# if __name__ == "__main__":
#     # Example usage
#     publisher = ImagePublisher()
    
#     # Configure RGB camera with custom settings
#     rgb_config = CameraConfig(
#         width=640,
#         height=480,
#         camera_id=0,
#         fourcc='MJPG'
#     )
#     publisher.setup_rgb_camera(rgb_config)
    
#     # Configure depth camera with custom settings
#     depth_config = CameraConfig(
#         width=640,
#         height=480,
#         fps=60,  # Lower FPS for depth is typical
#         camera_id=1,
#         fourcc='MJPG'
#     )
#     publisher.setup_depth_camera(depth_config)

    
#     # Start publishing frames
#     publisher.publish_test_frames()
################################################################



def image_RGB_to_ndarray(imageR: list[float], imageG: list[float], imageB: list[float], resolutionX: int, resolutionY: int):
    # Interleave RGB data
    rgb_array = np.zeros((resolutionY, resolutionX, 3), dtype=np.uint8)
    rgb_array[:, :, 0] = np.array(imageR, dtype=np.uint8).reshape((resolutionY, resolutionX))
    rgb_array[:, :, 1] = np.array(imageG, dtype=np.uint8).reshape((resolutionY, resolutionX))
    rgb_array[:, :, 2] = np.array(imageB, dtype=np.uint8).reshape((resolutionY, resolutionX))
    return rgb_array

def image_Depth_to_ndarray(
    pixels: Any, resolutionX: int, resolutionY: int,
    *, max_cm: float = 20_000.0, nodata: float = 9_999_999.0, rng: np.random.Generator | None = None
    ) -> np.ndarray:

    count = resolutionX * resolutionY

    # Fast path for buffer-like inputs (bytes/bytearray/memoryview/NumPy array)
    if isinstance(pixels, (bytes, bytearray, memoryview)):
        arr = np.frombuffer(pixels, dtype=np.float32, count=count)
        # bytes -> often read-only; make writable if needed
        if not arr.flags.writeable:
            arr = arr.copy()
    elif isinstance(pixels, np.ndarray) and pixels.dtype == np.float32 and pixels.size == count:
        # Zero-copy reshape if already a flat float32 array
        arr = pixels
    else:
        # General fallback for Python lists or other iterables
        arr = np.asarray(pixels, dtype=np.float32)

    # Ensure expected size before reshape (helpful for debugging)
    if arr.size != count:
        raise ValueError(f"Depth buffer size {arr.size} != {count} (X={resolutionX}, Y={resolutionY})")

    # Make sure it's contiguous & writable for in-place ops
    if not (arr.flags.c_contiguous and arr.flags.writeable):
        arr = np.ascontiguousarray(arr)

    arr = arr.reshape((resolutionY, resolutionX))

    # Add ±0.3 cm Gaussian noise, in-place
    if rng is None:
        rng = np.random.default_rng()
    noise = rng.normal(0.0, 0.3, arr.shape).astype(np.float32)
    np.add(arr, noise, out=arr)

    # Mark values beyond max range as nodata (one pass)
    arr[arr > max_cm] = nodata

    return arr

#######################################
# BEGIN MAIN SCRIPT
#######################################

st.path_utils.EnsureUserSpecificDirsExist() # Shouldn't be needed, but just in case
out_folder = st.path_utils.GetLocalOutputDir()

Filename : str = st.GetThisSystem().GetParam(st.VarType.string, "Filename")

output_full_filepath = os.path.join(out_folder, Filename)
os.makedirs(output_full_filepath, exist_ok=True)


this = st.GetThisSystem()
camera: st.Entity = this.GetParam(st.VarType.entityRef, "Camera")

# Camera stuff
capture_id = 0

def capture_image(camera: st.Entity):
    global capture_id

    capture_id += 1
    # st.logger_info(f"Capturing image with ID: {capture_id}")
    properties = st.CaptureImageProperties()
    properties.ResolutionX = camera.GetParam(st.VarType.int32, "ResolutionX")
    properties.ResolutionY = camera.GetParam(st.VarType.int32, "ResolutionY")
    properties.FOV = camera.GetParam(st.VarType.double, "FOV")
    properties.nonphys_EV = camera.GetParam(st.VarType.double, "Exposure")
    properties.CaptureID = capture_id
    properties.output_mode = st.OutputMode.RGB_LDR_sRGB

    id = st.camera.CaptureImage(camera, properties)
    return id

def capture_image_depth(camera: st.Entity):
    global capture_id

    capture_id += 1
    # st.logger_info(f"Capturing image with ID: {capture_id}")
    properties = st.CaptureImageProperties()
    properties.ResolutionX = camera.GetParam(st.VarType.int32, "ResolutionX")
    properties.ResolutionY = camera.GetParam(st.VarType.int32, "ResolutionY")
    properties.FOV = camera.GetParam(st.VarType.double, "FOV")
    properties.nonphys_EV = camera.GetParam(st.VarType.double, "Exposure")
    properties.CaptureID = capture_id
    properties.output_mode = st.OutputMode.Depth_cm

    id = st.camera.CaptureImage(camera, properties)
    return id

#UNUSED IN THIS SCRIPT BY DEFAULT
def ProcessImage_Save_RGB(image : st.camera.CapturedImage):
    capID = image.properties.CaptureID
    resx = image.properties.ResolutionX
    resy = image.properties.ResolutionY
    projectionMat = image.properties.ProjectionMatrix
    # st.logger_info("Projection Matrix: " + str(projectionMat))

    timestamp = image.get_timestamp().as_tai_string()

    # st.logger_info("Image resolution: [" + str(resx) + ", " + str(resy) + "]")
    img_r = np.array(image.as_RGB8().PixelsR, dtype=np.uint8).reshape((resy, resx))
    img_g = np.array(image.as_RGB8().PixelsG, dtype=np.uint8).reshape((resy, resx))
    img_b = np.array(image.as_RGB8().PixelsB, dtype=np.uint8).reshape((resy, resx))

    # Stack channels into a single 3D array (height x width x 3)

    output_filename = f"{output_full_filepath}/image_{capID:07d}"

    # OpenCV uses BGR ordering
    img_bgr = np.stack((img_b, img_g, img_r), axis=-1)
    cv2.imwrite(output_filename + ".jpg", img_bgr)

    metadata = { "Timestamp": timestamp }
    json.dump(metadata, open(output_filename + ".json", "w"))
    # st.OnScreenLogMessage(f"Saved Image {capID}", "CamTest", st.Severity.Info)

#UNUSED IN THIS SCRIPT BY DEFAULT
def ProcessImage_Save_Depth(image : st.camera.CapturedImage_f32):
    capID = image.properties.CaptureID
    resx = image.properties.ResolutionX
    resy = image.properties.ResolutionY
    projectionMat = image.properties.ProjectionMatrix
    # st.logger_info("Projection Matrix: " + str(projectionMat))

    timestamp = image.get_timestamp().as_tai_string()

    # st.logger_info("Image resolution: [" + str(resx) + ", " + str(resy) + "]")
    img = np.array(image.as_f32().Pixels, dtype=np.float32).reshape((resy, resx))

    output_filename = f"{output_full_filepath}/depth_{capID:07d}"

    # OpenCV saving
    cv2.imwrite(output_filename + ".tif", img)

    # Output JSON metadata
    metadata = { "Timestamp": timestamp }
    json.dump(metadata, open(output_filename + ".json", "w"))
    # st.OnScreenLogMessage(f"Saved Image {capID}", "CamTest", st.Severity.Info)


def imageReceived(capturedImage: st.camera.CapturedImage):
    resx = capturedImage.properties.ResolutionX
    resy = capturedImage.properties.ResolutionY
    projectionMat = capturedImage.properties.ProjectionMatrix
    # st.logger_info(f"Image received with ID: {capturedImage.properties.CaptureID}, Resolution: {resx}x{resy}, FOV: {capturedImage.properties.FOV}, Projection Matrix: {projectionMat}, Output Mode: {capturedImage.properties.output_mode}")

    if capturedImage.properties.output_mode == st.OutputMode.RGB_LDR_sRGB:
        img: st.camera.CapturedImage_RGB8 = capturedImage.as_RGB8()
        rgb_array = image_RGB_to_ndarray(img.PixelsR, img.PixelsG, img.PixelsB, resx, resy)
        # Saving for debug purposes
        # ProcessImage_Save_RGB(capturedImage)
        publisher.publish_RGB_frame(rgb_array)
      
    elif capturedImage.properties.output_mode == st.OutputMode.Depth_cm:
        img: st.camera.CapturedImage_f32 = capturedImage.as_f32()
        d_array = image_Depth_to_ndarray(img.Pixels, resx, resy)
        # Saving for debug purposes
        # ProcessImage_Save_Depth(capturedImage)
        publisher.publish_Depth_frame(d_array)



publisher = ImagePublisher("0.0.0.0", 55556)


# Configure RGB camera with custom settings
rgb_config = CameraConfig(
    width=512,
    height=512
)
publisher.setup_rgb_camera(rgb_config)

# Configure depth camera with custom settings
depth_config = CameraConfig(
    width=512,
    height=512
)
publisher.setup_depth_camera(depth_config)


################## Main Loop #####################
exit_flag = False
frame_rate = this.GetParam(st.VarType.double, "LoopFreqHz")

RGB_timer = 0.0
Depth_timer = 0.0

st.OnScreenLogMessage(f"Starting ImageSender Loop", "CamTest", st.Severity.Info)

while not exit_flag:
    time.sleep(1.0 / frame_rate)
    dt = 1.0 / frame_rate
    RGB_timer += dt
    Depth_timer += dt

    RGB_period = 1.0/camera.GetParam(st.VarType.double, "RGB_FreqHz")
    Depth_period = 1.0/camera.GetParam(st.VarType.double, "Depth_FreqHz")
    
    if(RGB_timer >= RGB_period):
        # st.OnScreenLogMessage(f"RGB cmd freq: {camera.GetParam(st.VarType.double, 'RGB_FreqHz')}, Depth cmd freq: {camera.GetParam(st.VarType.double, 'Depth_FreqHz')}", "CamTest", st.Severity.Info)
        RGB_timer = 0.0
        capture_id = capture_image(camera)
        st.camera.OnImageReceived(capture_id, lambda capturedImage: imageReceived(capturedImage))

    if(Depth_timer >= Depth_period):
        # st.OnScreenLogMessage(f"RGB cmd freq: {camera.GetParam(st.VarType.double, 'RGB_FreqHz')}, Depth cmd freq: {camera.GetParam(st.VarType.double, 'Depth_FreqHz')}", "CamTest", st.Severity.Info)
        Depth_timer = 0.0
        capture_id = capture_image_depth(camera)
        st.camera.OnImageReceived(capture_id, lambda capturedImage: imageReceived(capturedImage))

st.leave_sim()
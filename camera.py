import PyIndi
import time
import sys
import threading

import numpy as np
from astropy.io import fits
import io
import matplotlib.pyplot as plt


class IndiClient(PyIndi.BaseClient):
    def __init__(self, device="Bresser GPCMOS02000KPA", host="localhost", port=7624):
        super(IndiClient, self).__init__()
        self.device = device
        self.host = host
        self.port = port
        self.device_ccd = None
        self.generic_properties = []
        self.blob_event = threading.Event()
        self.blob_event.clear()

        # Connect to the server
        self.connect_server()

        # Get device
        self.get_device()

        # Connect to the device
        self.connect_device()

        # Get exposure and controls properties
        self.ccd_exposure = self.device_ccd.getNumber("CCD_EXPOSURE")
        print("Exposure created")
        self.ccd_gain = self.device_ccd.getNumber("CCD_CONTROLS")
        print("Gain created")

        # Inform to indi server we want to receive blob from CCD1
        self.setBLOBMode(PyIndi.B_ALSO, self.device, "CCD1")

        # Get blob
        self.ccd_ccd1 = self.device_ccd.getBLOB("CCD1")

        # Fix frame bug
        self.set_ccd_capture_format("INDI_RAW(RAW 16)")

    def updateProperty(self, prop):
        if prop.getType() == PyIndi.INDI_BLOB:
            # print("new BLOB ", prop.getName())
            self.blob_event.set()

    def connect_server(self):
        self.setServer(hostname=self.host, port=self.port)
        if not self.connectServer():
            print(
                "No indiserver running on "
                + self.getHost()
                + ":"
                + str(self.getPort())
                + " - Try to run"
            )
            print("  indiserver indi_simulator_telescope indi_simulator_ccd")
            sys.exit(1)
        time.sleep(1)
        print("Connected to indi server")

    def get_devices(self):
        device_list = self.getDevices()
        for device in device_list:
            print(f"   > {device.getDeviceName()}")

    def get_device(self):
        self.device_ccd = self.getDevice(self.device)
        while not self.device_ccd:
            time.sleep(0.5)
            self.device_ccd = self.getDevice(self.device)
        print(f"{self.device_ccd.getDeviceName()} found")

    def connect_device(self):
        ccd_connect = self.device_ccd.getSwitch("CONNECTION")
        while not ccd_connect:
            time.sleep(0.5)
            ccd_connect = self.device_ccd.getSwitch("CONNECTION")
        if not (self.device_ccd.isConnected()):
            ccd_connect.reset()
            ccd_connect[0].setState(PyIndi.ISS_ON)  # the "CONNECT" switch
            self.sendNewSwitch(ccd_connect)
        print(f"{self.device} connected")

    def get_properties(self):
        generic_properties = self.device_ccd.getProperties()
        for generic_property in generic_properties:
            print(f"   > {generic_property.getName()} {generic_property.getTypeAsString()}")
            self.generic_properties.append((generic_property.getName(), generic_property.getTypeAsString()))
            if generic_property.getType() == PyIndi.INDI_TEXT:
                for widget in PyIndi.PropertyText(generic_property):
                    print(f"       {widget.getName()}({widget.getLabel()}) = {widget.getText()}")

            if generic_property.getType() == PyIndi.INDI_NUMBER:
                for widget in PyIndi.PropertyNumber(generic_property):
                    print(f"       {widget.getName()}({widget.getLabel()}) = {widget.getValue()}")

            if generic_property.getType() == PyIndi.INDI_SWITCH:
                for widget in PyIndi.PropertySwitch(generic_property):
                    print(f"       {widget.getName()}({widget.getLabel()}) = {widget.getStateAsString()}")

            if generic_property.getType() == PyIndi.INDI_LIGHT:
                for widget in PyIndi.PropertyLight(generic_property):
                    print(f"       {widget.getLabel()}({widget.getLabel()}) = {widget.getStateAsString()}")

            if generic_property.getType() == PyIndi.INDI_BLOB:
                for widget in PyIndi.PropertyBlob(generic_property):
                    print(f"       {widget.getName()}({widget.getLabel()}) = <blob {widget.getSize()} bytes>")

        return 0

    def set_exposure(self, exposure):
        self.ccd_exposure[0].setValue(exposure)
        self.sendNewNumber(self.ccd_exposure)
        self.blob_event.wait()
        self.blob_event.clear()

    def set_gain(self, gain):
        self.ccd_gain[0].setValue(gain)
        self.sendNewNumber(self.ccd_gain)
        # self.blob_event.wait()
        self.blob_event.clear()
        print(f"Gain set to {gain}")

    def set_ccd_capture_format(self, capture_format="INDI_RGB(RGB)"):
        # Capture format
        ccd_capture_format = self.device_ccd.getSwitch("CCD_CAPTURE_FORMAT")

        # Transfer format
        ccd_transfer_format = self.device_ccd.getSwitch("CCD_TRANSFER_FORMAT")

        # Set the format
        if capture_format == "INDI_RGB(RGB)":
            ccd_capture_format[0].setState(PyIndi.ISS_ON)
            ccd_transfer_format[0].setState(PyIndi.ISS_OFF)
            ccd_capture_format[1].setState(PyIndi.ISS_OFF)
            ccd_transfer_format[1].setState(PyIndi.ISS_ON)
        elif capture_format == "INDI_RAW(RAW 16)":
            ccd_capture_format[0].setState(PyIndi.ISS_OFF)
            ccd_transfer_format[0].setState(PyIndi.ISS_ON)
            ccd_capture_format[1].setState(PyIndi.ISS_ON)
            ccd_transfer_format[1].setState(PyIndi.ISS_OFF)
        self.sendNewSwitch(ccd_capture_format)
        self.sendNewSwitch(ccd_transfer_format)
        self.blob_event.clear()
        print("Image format fixed")

        return 0

    def capture(self, exposure=1, n_frames=10):
        ii = 0
        while ii < n_frames:
            ii += 1
            print(f"Capturing frame {ii} of {n_frames}")

            # Trigger image acquisition
            self.set_exposure(exposure)

            # Get fits from blob and extract image
            blob = self.ccd_ccd1[0]
            fits_data = blob.getblobdata()
            hdul = fits.open(io.BytesIO(fits_data))
            image_data = hdul[0].data

            # Define color limits (you can set them manually or based on the image statistics)
            vmin = np.percentile(image_data, 5)  # 5th percentile
            vmax = np.percentile(image_data, 95)  # 95th percentile

            # Display the image
            if image_data is not None:
                plt.figure(figsize=(8, 8))
                plt.imshow(image_data, cmap='gray', origin='lower', vmin=vmin, vmax=vmax)
                plt.title("Picture")
                plt.colorbar(label="Pixel value")
                plt.show()
            else:
                print("No image data found in FITS file.")
            hdul.close()
            print(f"Frame {ii} of {n_frames} captured!")


if __name__ == "__main__":
    client = IndiClient()
    client.set_gain(400)
    client.capture(exposure=1, n_frames=2)
    print("Ready!")
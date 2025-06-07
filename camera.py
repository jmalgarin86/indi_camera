import PyIndi
import time
import sys
import threading
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
        self.last_blob = None

        # Shows the indi version used in the code
        x = PyIndi.INDI_VERSION_MAJOR
        y = PyIndi.INDI_VERSION_MINOR
        z = PyIndi.INDI_VERSION_RELEASE
        print(f"PyIndi version: {x}.{y}.{z}")

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
        print(f"   > {self.device_ccd.getDeviceName()}")

    def connect_device(self):
        ccd_connect = self.device_ccd.getSwitch("CONNECTION")
        while not ccd_connect:
            time.sleep(0.5)
            ccd_connect = self.device_ccd.getSwitch("CONNECTION")
        if not (self.device_ccd.isConnected()):
            ccd_connect.reset()
            ccd_connect[0].setState(PyIndi.ISS_ON)  # the "CONNECT" switch
            self.sendNewSwitch(ccd_connect)
        print("Device connected")

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
        ccd_exposure = self.device_ccd.getNumber("CCD_EXPOSURE")
        while not ccd_exposure:
            time.sleep(0.5)
            ccd_exposure = self.device_ccd.getNumber("CCD_EXPOSURE")
        ccd_exposure[0].setValue(exposure)
        self.sendNewNumber(ccd_exposure)

    def set_ccd_capture_format(self, capture_format="INDI_RGB(RGB)"):
        # Capture format
        ccd_capture_format = self.device_ccd.getSwitch("CCD_CAPTURE_FORMAT")
        while not ccd_capture_format:
            time.sleep(0.5)
            ccd_capture_format = self.device_ccd.getSwitch("CCD_CAPTURE_FORMAT")

        # Transfer format
        ccd_transfer_format = self.device_ccd.getSwitch("CCD_TRANSFER_FORMAT")
        while not ccd_transfer_format:
            time.sleep(0.5)
            ccd_transfer_format = self.device_ccd.getSwitch("CCD_TRANSFER_FORMAT")

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

if __name__ == "__main__":
    client = IndiClient()
    client.connect_server()
    client.get_device()
    client.connect_device()
    client.set_exposure(0.1)
    client.set_ccd_capture_format("INDI_RGB(RGB)")
    client.get_properties()
    print("Ready!")
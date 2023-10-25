import time
import RNS

from kivy.metrics import dp,sp
from kivy.lang.builder import Builder
from kivy.core.clipboard import Clipboard
from kivymd.uix.recycleview import MDRecycleView
from kivymd.uix.list import OneLineIconListItem
from kivy.properties import StringProperty, BooleanProperty
from kivy.effects.scroll import ScrollEffect
from kivy.clock import Clock
from sideband.sense import Telemeter
import threading
import webbrowser

from datetime import datetime


if RNS.vendor.platformutils.get_platform() == "android":
    from ui.helpers import ts_format
else:
    from .helpers import ts_format

class ObjectDetails():
    def __init__(self, app, object_hash = None):
        self.app = app
        self.widget = None
        self.object_hash = object_hash
        self.coords = None
        self.raw_telemetry = None
        self.from_conv = False

        if not self.app.root.ids.screen_manager.has_screen("object_details_screen"):
            self.screen = Builder.load_string(layou_object_details)
            self.screen.app = self.app
            self.screen.delegate = self
            self.ids = self.screen.ids
            self.app.root.ids.screen_manager.add_widget(self.screen)

            self.screen.ids.object_details_scrollview.effect_cls = ScrollEffect
            self.telemetry_list = RVDetails()
            self.telemetry_list.delegate = self
            self.telemetry_list.app = self.app
            self.screen.ids.object_details_scrollview.add_widget(self.telemetry_list)

    def close_action(self, sender=None):
        if self.from_conv:
            self.app.open_conversation(self.object_hash, direction="right")
        else:
            self.app.close_sub_map_action()

    def set_source(self, source_dest, from_conv=False):
        self.object_hash = source_dest

        if from_conv:
            self.from_conv = True
        else:
            self.from_conv = False

        self.coords = None
        self.telemetry_list.data = []
        appearance = self.app.sideband.peer_appearance(source_dest)
        self.screen.ids.name_label.text = self.app.sideband.peer_display_name(source_dest)
        self.screen.ids.coordinates_button.disabled = True
        self.screen.ids.object_appearance.icon = appearance[0]
        self.screen.ids.object_appearance.icon_color = appearance[1]
        self.screen.ids.object_appearance.md_bg_color = appearance[2]

        latest_telemetry = self.app.sideband.peer_telemetry(source_dest, limit=1)
        if latest_telemetry != None and len(latest_telemetry) > 0:
            own_address = self.app.sideband.lxmf_destination.hash
            telemeter = Telemeter.from_packed(latest_telemetry[0][1])
            self.raw_telemetry = telemeter.read_all()

            relative_to = None
            if source_dest != own_address:
                relative_to = self.app.sideband.telemeter

            rendered_telemetry = telemeter.render(relative_to=relative_to)
            if "location" in telemeter.sensors:
                def job(dt):
                    self.screen.ids.coordinates_button.disabled = False
                Clock.schedule_once(job, 0.01)
                
            self.telemetry_list.update_source(rendered_telemetry)
            def job(dt):
                self.screen.ids.telemetry_button.disabled = False
            Clock.schedule_once(job, 0.01)
        else:
            def job(dt):
                self.screen.ids.telemetry_button.disabled = True
            Clock.schedule_once(job, 0.01)
            self.telemetry_list.update_source(None)

        self.screen.ids.object_details_scrollview.effect_cls = ScrollEffect

    def reload(self):
        self.clear_widget()
        self.update()

    def clear_widget(self):
        pass

    def update(self):
        us = time.time()
        self.update_widget()        
        RNS.log("Updated object details in "+RNS.prettytime(time.time()-us), RNS.LOG_DEBUG)

    def update_widget(self):
        if self.widget == None:
            self.widget = MDLabel(text=RNS.prettyhexrep(self.object_hash))

    def get_widget(self):
        return self.widget

    def copy_coordinates(self, sender=None):
        Clipboard.copy(str(self.coords or "No data"))

    def copy_telemetry(self, sender=None):
        Clipboard.copy(str(self.raw_telemetry or "No data"))

class ODView(OneLineIconListItem):
    icon = StringProperty()
    def __init__(self):
        super().__init__()

class RVDetails(MDRecycleView):
    def __init__(self):
        super().__init__()
        self.data = []

    def update_source(self, rendered_telemetry=None):
        if not rendered_telemetry:
            rendered_telemetry = []
        
        sort = {
            "Physical Link": 10,
            "Location": 20,
            "Ambient Light": 30,
            "Ambient Temperature": 40,
            "Relative Humidity": 50,
            "Ambient Pressure": 60,
            "Battery": 70,
            "Timestamp": 80,    
        }
        self.entries = []
        rendered_telemetry.sort(key=lambda s: sort[s["name"]] if s["name"] in sort else 1000)
        for s in rendered_telemetry:
            extra_entries = []
            def pass_job(sender=None):
                pass
            release_function = pass_job
            formatted_values = None
            name = s["name"]
            if name == "Timestamp":
                ts = s["values"]["UTC"]
                if ts != None:
                    ts_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                    formatted_values = f"Recorded [b]{RNS.prettytime(time.time()-ts, compact=True)} ago[/b] ({ts_str})"
            elif name == "Battery":
                p = s["values"]["percent"]
                cs = s["values"]["_meta"]
                if cs != None: cs_str = f" ({cs})"
                if p != None: formatted_values = f"{name} [b]{p}%[/b]"+cs_str
            elif name == "Ambient Pressure":
                p = s["values"]["mbar"]
                if p != None: formatted_values = f"{name} [b]{p} mbar[/b]"
                dt = "mbar"
                if "deltas" in s and dt in s["deltas"] and s["deltas"][dt] != None:
                    d = s["deltas"][dt]
                    formatted_values += f"  (Δ = {d} mbar)"
            elif name == "Ambient Temperature":
                c = s["values"]["c"]
                if c != None: formatted_values = f"{name} [b]{c}° C[/b]"
                dt = "c"
                if "deltas" in s and dt in s["deltas"] and s["deltas"][dt] != None:
                    d = s["deltas"][dt]
                    formatted_values += f"  (Δ = {d}° C)"
            elif name == "Relative Humidity":
                r = s["values"]["percent"]
                if r != None: formatted_values = f"{name} [b]{r}%[/b]"
                dt = "percent"
                if "deltas" in s and dt in s["deltas"] and s["deltas"][dt] != None:
                    d = s["deltas"][dt]
                    formatted_values += f"  (Δ = {d}%)"
            elif name == "Physical Link":
                rssi = s["values"]["rssi"]; rssi_str = None
                snr = s["values"]["snr"]; snr_str = None
                q = s["values"]["q"]; q_str = None
                if q != None: q_str = f"Link Quality [b]{q}%[/b]"
                if rssi != None:
                    rssi_str = f"RSSI [b]{rssi} dBm[/b]"
                    if q != None: rssi_str = ", "+rssi_str
                if snr != None:
                    snr_str = f"SNR [b]{snr} dB[/b]"
                    if q != None or rssi != None: snr_str = ", "+snr_str
                if q_str or rssi_str or snr_str:
                    formatted_values = q_str+rssi_str+snr_str
            elif name == "Location":
                lat = s["values"]["latitude"]
                lon = s["values"]["longtitude"]
                alt = s["values"]["altitude"]
                speed = s["values"]["speed"]
                heading = s["values"]["heading"]
                accuracy = s["values"]["accuracy"]
                updated = s["values"]["updated"]
                updated_str = f", logged [b]{RNS.prettytime(time.time()-updated, compact=True)} ago[/b]"

                coords = f"{lat}, {lon}"
                self.delegate.coords = coords
                formatted_values = f"Coordinates [b]{coords}[/b], altitude [b]{alt} meters[/b]"
                speed_formatted_values = f"Speed [b]{speed} Km/h[/b], heading [b]{heading}°[/b]"
                extra_formatted_values = f"Uncertainty [b]{accuracy} meters[/b]"+updated_str

                data = {"icon": s["icon"], "text": f"{formatted_values}"}

                if "distance" in s:
                    distance_formatted_text = ""
                    if "orthodromic" in s["distance"]:
                        od = s["distance"]["orthodromic"]
                        if od != None:
                            od_text = f"Geodesic distance [b]{RNS.prettydistance(od)}[/b]"
                            distance_formatted_text += od_text
                    
                    if "euclidian" in s["distance"]:
                        ed = s["distance"]["euclidian"]
                        if ed != None:
                            ed_text = f"euclidian distance [b]{RNS.prettydistance(ed)}[/b]"
                            if len(distance_formatted_text) != 0:
                                distance_formatted_text += ", "
                            else:
                                ed_text = ed_text.replace("euclidian", "Euclidian")
                            distance_formatted_text += ed_text

                    extra_entries.append({"icon": "earth", "text": distance_formatted_text})

                if "azalt" in s:
                    azalt_formatted_text = ""
                    if "azimuth" in s["azalt"]:
                        az = s["azalt"]["azimuth"]
                        az_text = f"Azimuth [b]{round(az,4)}°[/b]"
                        azalt_formatted_text += az_text
                    
                    if "altitude" in s["azalt"]:
                        al = s["azalt"]["altitude"]
                        al_text = f"altitude [b]{round(al,4)}°[/b]"
                        if len(azalt_formatted_text) != 0: azalt_formatted_text += ", "
                        azalt_formatted_text += al_text

                    if "above_horizon" in s["azalt"]:
                        astr = "above" if s["azalt"]["above_horizon"] == True else "below"
                        ah_text = f"object is [b]{astr}[/b] the horizon"
                        if len(azalt_formatted_text) != 0: azalt_formatted_text += ", "
                        azalt_formatted_text += ah_text

                    extra_entries.append({"icon": "compass-rose", "text": azalt_formatted_text})

                if "radio_horizon" in s:
                    crange_text = RNS.prettydistance(s["radio_horizon"]["combined_range"])
                    if s["radio_horizon"]["within_range"]:
                        rh_formatted_text = f"Object is [b]within[/b] combined radio horizon of [b]{crange_text}[/b]"
                    else:
                        rh_formatted_text = f"Object is [b]not within[/b] within combined radio horizon of [b]{crange_text}[/b]"
                    
                    extra_entries.append({"icon": "radio-tower", "text": rh_formatted_text})

                extra_entries.append({"icon": "map-marker-question", "text": extra_formatted_values})
                extra_entries.append({"icon": "speedometer", "text": speed_formatted_values})

                def select(e=None):
                    geo_uri = f"geo:{lat},{lon}"
                    def lj():
                        webbrowser.open(geo_uri)
                    threading.Thread(target=lj, daemon=True).start()

                release_function = select
            else:
                formatted_values = f"{name}"
                for vn in s["values"]:
                    v = s["values"][vn]
                    formatted_values += f" [b]{v} {vn}[/b]"

                    dt = vn
                    if "deltas" in s and dt in s["deltas"] and s["deltas"][dt] != None:
                        d = s["deltas"][dt]
                        formatted_values += f"  (Δ = {d} {vn})"
            
            data = None
            if formatted_values != None:
                if release_function:
                    data = {"icon": s["icon"], "text": f"{formatted_values}", "on_release": release_function}
                else:
                    data = {"icon": s["icon"], "text": f"{formatted_values}"}

            if data != None:
                self.entries.append(data)
            for extra in extra_entries:
                self.entries.append(extra)

        if len(self.entries) == 0:
            self.entries.append({"icon": "account-question-outline", "text": f"No information known about this peer"})

        self.data = self.entries



layou_object_details = """
#:import MDLabel kivymd.uix.label.MDLabel
#:import OneLineIconListItem kivymd.uix.list.OneLineIconListItem
#:import Button kivy.uix.button.Button

<ODView>
    IconLeftWidget:
        icon: root.icon

<RVDetails>:
    viewclass: "ODView"
    RecycleBoxLayout:
        default_size: None, dp(50)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: "vertical"

MDScreen:
    name: "object_details_screen"
    
    BoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            id: details_bar
            title: "Details"
            anchor_title: "left"
            elevation: 0
            left_action_items:
                [['menu', lambda x: root.app.nav_drawer.set_state("open")]]
            right_action_items:
                [
                ['close', lambda x: root.delegate.close_action()],
                ]

        MDBoxLayout:
            id: object_header
            orientation: "horizontal"
            spacing: dp(24)
            size_hint_y: None
            height: self.minimum_height
            padding: dp(24)

            MDIconButton:
                id: object_appearance
                icon: "map-marker-star-outline"
                icon_color: [0,0,0,1]
                md_bg_color: [1,1,1,1]
                theme_icon_color: "Custom"
                icon_size: dp(32)

            MDLabel:
                id: name_label
                markup: True
                text: "Object Name"
                font_style: "H6"

        MDBoxLayout:
            id: object_header
            orientation: "horizontal"
            spacing: dp(24)
            size_hint_y: None
            height: self.minimum_height
            padding: [dp(24), dp(0), dp(24), dp(12)]

            MDRectangleFlatIconButton:
                id: telemetry_button
                icon: "content-copy"
                text: "Copy Telemetry"
                padding: [dp(0), dp(14), dp(0), dp(14)]
                icon_size: dp(24)
                font_size: dp(16)
                size_hint: [1.0, None]
                on_release: root.delegate.copy_telemetry(self)
                disabled: False

            MDRectangleFlatIconButton:
                id: coordinates_button
                icon: "map-marker-outline"
                text: "Copy Coordinates"
                padding: [dp(0), dp(14), dp(0), dp(14)]
                icon_size: dp(24)
                font_size: dp(16)
                size_hint: [1.0, None]
                on_release: root.delegate.copy_coordinates(self)
                disabled: False
            
        ScrollView:
            id: object_details_scrollview
            effect_cls: "ScrollEffect"
                
"""
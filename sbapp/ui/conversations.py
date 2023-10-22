import RNS
import time

from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivymd.uix.list import MDList, IconLeftWidget, IconRightWidget, OneLineAvatarIconListItem
from kivymd.uix.menu import MDDropdownMenu
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.effects.scroll import ScrollEffect

from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.dialog import MDDialog

from kivy.lang.builder import Builder

class NewConv(BoxLayout):
    pass

class MsgSync(BoxLayout):
    pass

class ConvSettings(BoxLayout):
    disp_name = StringProperty()
    context_dest = StringProperty()
    trusted = BooleanProperty()
    telemetry = BooleanProperty()

class Conversations():
    def __init__(self, app):
        self.app = app
        self.context_dests = []
        self.added_item_dests = []
        self.list = None
        self.ids = None

        if not self.app.root.ids.screen_manager.has_screen("conversations_screen"):
            self.screen = Builder.load_string(conv_screen_kv)
            self.ids = self.screen.ids
            self.app.root.ids.screen_manager.add_widget(self.screen)
        
        self.conversation_dropdown = None
        self.delete_dialog = None
        self.clear_dialog = None
        self.clear_telemetry_dialog = None

        self.update()

    def reload(self):
        self.clear_list()
        self.update()

    def clear_list(self):
        if self.list != None:
            self.list.clear_widgets()

        self.context_dests = []
        self.added_item_dests = []

    def update(self):
        # if self.app.sideband.getstate("app.flags.unread_conversations"):
        #     self.clear_list()
        
        self.context_dests = self.app.sideband.list_conversations()
        self.update_widget()

        self.app.sideband.setstate("app.flags.unread_conversations", False)
        self.app.sideband.setstate("app.flags.new_conversations", False)
        self.app.sideband.setstate("wants.viewupdate.conversations", False)

    def trust_icon(self, context_dest, unread):
        trust_icon = "account-question"
        if self.app.sideband.is_trusted(context_dest):
            if unread:
                trust_icon = "email-seal"
            else:
                trust_icon = "account-check"
        else:
            if unread:
                trust_icon = "email"
            else:
                trust_icon = "account-question"

        return trust_icon

    def update_widget(self):
        us = time.time()
        RNS.log("Updating conversation list widgets", RNS.LOG_DEBUG)
        if self.list == None:
            self.list = MDList()

        remove_widgets = []
        for w in self.list.children:
            if not w.sb_uid in [e["dest"] for e in self.context_dests]:
                RNS.log("Should remove "+RNS.prettyhexrep(w.sb_uid)+" from list")
                remove_widgets.append(w)
                self.added_item_dests.remove(w.sb_uid)

        for w in remove_widgets:
            RNS.log("Removing "+str(w))
            self.list.remove_widget(w)

            
        for conv in self.context_dests:
            context_dest = conv["dest"]
            unread = conv["unread"]
            last_activity = conv["last_activity"]

            if not context_dest in self.added_item_dests:
                iconl = IconLeftWidget(icon=self.trust_icon(context_dest, unread), on_release=self.app.conversation_action)
                item = OneLineAvatarIconListItem(text=self.app.sideband.peer_display_name(context_dest), on_release=self.app.conversation_action)
                item.add_widget(iconl)
                item.last_activity = last_activity
                item.iconl = iconl
                item.sb_uid = context_dest
                item.sb_unread = unread
                iconl.sb_uid = context_dest

                def gen_edit(item):
                    def x():
                        t_s = time.time()
                        dest = self.conversation_dropdown.context_dest
                        try:
                            disp_name = self.app.sideband.raw_display_name(dest)
                            is_trusted = self.app.sideband.is_trusted(dest)
                            send_telemetry = self.app.sideband.should_send_telemetry(dest)

                            yes_button = MDRectangleFlatButton(text="Save",font_size=dp(18), theme_text_color="Custom", line_color=self.app.color_accept, text_color=self.app.color_accept)
                            no_button = MDRectangleFlatButton(text="Cancel",font_size=dp(18))
                            dialog_content = ConvSettings(disp_name=disp_name, context_dest=RNS.hexrep(dest, delimit=False), trusted=is_trusted, telemetry=send_telemetry)
                            dialog = MDDialog(
                                title="Edit Conversation",
                                text= "With "+RNS.prettyhexrep(dest),
                                type="custom",
                                content_cls=dialog_content,
                                buttons=[ yes_button, no_button ],
                                # elevation=0,
                            )
                            dialog.d_content = dialog_content
                            def dl_yes(s):
                                try:
                                    name = dialog.d_content.ids["name_field"].text
                                    trusted = dialog.d_content.ids["trusted_switch"].active
                                    telemetry = dialog.d_content.ids["telemetry_switch"].active
                                    if trusted:
                                        self.app.sideband.trusted_conversation(dest)
                                    else:
                                        self.app.sideband.untrusted_conversation(dest)

                                    if telemetry:
                                        self.app.sideband.send_telemetry_in_conversation(dest)
                                    else:
                                        self.app.sideband.no_telemetry_in_conversation(dest)

                                    self.app.sideband.named_conversation(name, dest)

                                except Exception as e:
                                    RNS.log("Error while saving conversation settings: "+str(e), RNS.LOG_ERROR)

                                dialog.dismiss()

                                def cb(dt):
                                    self.update()
                                Clock.schedule_once(cb, 0.2)

                            def dl_no(s):
                                dialog.dismiss()

                            yes_button.bind(on_release=dl_yes)
                            no_button.bind(on_release=dl_no)
                            item.dmenu.dismiss()
                            dialog.open()
                            RNS.log("Generated edit dialog in "+str(RNS.prettytime(time.time()-t_s)), RNS.LOG_DEBUG)

                        except Exception as e:
                            RNS.log("Error while creating conversation settings: "+str(e), RNS.LOG_ERROR)

                    return x

                def gen_clear(item):
                    def x():
                        if self.clear_dialog == None:
                            yes_button = MDRectangleFlatButton(text="Yes",font_size=dp(18), theme_text_color="Custom", line_color=self.app.color_reject, text_color=self.app.color_reject)
                            no_button = MDRectangleFlatButton(text="No",font_size=dp(18))

                            self.clear_dialog = MDDialog(
                                title="Clear all messages in conversation?",
                                buttons=[ yes_button, no_button ],
                                # elevation=0,
                            )
                            def dl_yes(s):
                                self.clear_dialog.dismiss()
                                self.app.sideband.clear_conversation(self.conversation_dropdown.context_dest)
                            def dl_no(s):
                                self.clear_dialog.dismiss()

                            yes_button.bind(on_release=dl_yes)
                            no_button.bind(on_release=dl_no)

                        item.dmenu.dismiss()
                        self.clear_dialog.open()
                    return x

                def gen_clear_telemetry(item):
                    def x():
                        if self.clear_telemetry_dialog == None:
                            yes_button = MDRectangleFlatButton(text="Yes",font_size=dp(18), theme_text_color="Custom", line_color=self.app.color_reject, text_color=self.app.color_reject)
                            no_button = MDRectangleFlatButton(text="No",font_size=dp(18))

                            self.clear_telemetry_dialog = MDDialog(
                                title="Clear all telemetry related to this peer?",
                                buttons=[ yes_button, no_button ],
                                # elevation=0,
                            )
                            def dl_yes(s):
                                self.clear_telemetry_dialog.dismiss()
                                self.app.sideband.clear_telemetry(self.conversation_dropdown.context_dest)
                            def dl_no(s):
                                self.clear_telemetry_dialog.dismiss()

                            yes_button.bind(on_release=dl_yes)
                            no_button.bind(on_release=dl_no)

                        item.dmenu.dismiss()
                        self.clear_telemetry_dialog.open()
                    return x

                def gen_del(item):
                    def x():
                        if self.delete_dialog == None:
                            yes_button = MDRectangleFlatButton(text="Yes",font_size=dp(18), theme_text_color="Custom", line_color=self.app.color_reject, text_color=self.app.color_reject)
                            no_button = MDRectangleFlatButton(text="No",font_size=dp(18))
                            self.delete_dialog = MDDialog(
                                title="Delete conversation?",
                                buttons=[ yes_button, no_button ],
                                # elevation=0,
                            )
                            def dl_yes(s):
                                self.delete_dialog.dismiss()
                                self.app.sideband.delete_conversation(self.conversation_dropdown.context_dest)
                                def cb(dt):
                                    self.update()
                                Clock.schedule_once(cb, 0.2)
                            def dl_no(s):
                                self.delete_dialog.dismiss()

                            yes_button.bind(on_release=dl_yes)
                            no_button.bind(on_release=dl_no)

                        item.dmenu.dismiss()
                        self.delete_dialog.open()
                    return x

                def gen_copy_addr(item):
                    def x():
                        Clipboard.copy(RNS.hexrep(self.conversation_dropdown.context_dest, delimit=False))
                        item.dmenu.dismiss()
                    return x

                item.iconr = IconRightWidget(icon="dots-vertical");

                if self.conversation_dropdown == None:
                    dmi_h = 40
                    dm_items = [
                        {
                            "viewclass": "OneLineListItem",
                            "text": "Edit",
                            "height": dp(dmi_h),
                            "on_release": gen_edit(item)
                        },
                        {
                            "text": "Copy Address",
                            "viewclass": "OneLineListItem",
                            "height": dp(dmi_h),
                            "on_release": gen_copy_addr(item)
                        },
                        {
                            "text": "Clear Messages",
                            "viewclass": "OneLineListItem",
                            "height": dp(dmi_h),
                            "on_release": gen_clear(item)
                        },
                        {
                            "text": "Clear Telemetry",
                            "viewclass": "OneLineListItem",
                            "height": dp(dmi_h),
                            "on_release": gen_clear_telemetry(item)
                        },
                        {
                            "text": "Delete Conversation",
                            "viewclass": "OneLineListItem",
                            "height": dp(dmi_h),
                            "on_release": gen_del(item)
                        }
                    ]

                    self.conversation_dropdown = MDDropdownMenu(
                        caller=item.iconr,
                        items=dm_items,
                        position="auto",
                        width=dp(256),
                        elevation=0,
                        radius=dp(3),
                    )
                    self.conversation_dropdown.effect_cls = ScrollEffect

                item.dmenu = self.conversation_dropdown

                def callback_factory(ref, dest):
                    def x(sender):
                        self.conversation_dropdown.context_dest = dest
                        ref.dmenu.caller = ref.iconr
                        ref.dmenu.open()
                    return x

                item.iconr.bind(on_release=callback_factory(item, context_dest))

                item.add_widget(item.iconr)

                item.trusted = self.app.sideband.is_trusted(context_dest)
                
                self.added_item_dests.append(context_dest)
                self.list.add_widget(item)

            else:
                for w in self.list.children:
                    if w.sb_uid == context_dest:
                        disp_name = self.app.sideband.peer_display_name(context_dest)
                        trust_icon = self.trust_icon(context_dest, unread)
                        w.last_activity = last_activity
                        if w.iconl.icon != trust_icon:
                            w.iconl.icon = trust_icon
                            w.sb_unread = unread
                        if w.text != disp_name:
                            w.text = disp_name

        self.list.children.sort(key=lambda w: (w.trusted, w.last_activity))

        RNS.log("Updated conversation list widgets in "+RNS.prettytime(time.time()-us), RNS.LOG_DEBUG)

    def get_widget(self):
        return self.list

conv_screen_kv = """
MDScreen:
    name: "conversations_screen"
    
    BoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Conversations"
            anchor_title: "left"
            elevation: 0
            left_action_items:
                [
                ['menu', lambda x: nav_drawer.set_state("open")],
                ]
            right_action_items:
                [
                ['access-point', lambda x: root.ids.screen_manager.app.announce_now_action(self)],
                ['webhook', lambda x: root.ids.screen_manager.app.connectivity_status(self)],
                ['qrcode', lambda x: root.ids.screen_manager.app.ingest_lxm_action(self)],
                ['email-sync', lambda x: root.ids.screen_manager.app.lxmf_sync_action(self)],
                ['account-plus', lambda x: root.ids.screen_manager.app.new_conversation_action(self)],
                ]

        ScrollView:
            id: conversations_scrollview
"""

Builder.load_string("""
<NewConv>
    orientation: "vertical"
    spacing: "24dp"
    size_hint_y: None
    height: dp(250)

    MDTextField:
        id: n_address_field
        max_text_length: 32
        hint_text: "Address"
        helper_text: "Error, check your input"
        helper_text_mode: "on_error"
        text: ""
        font_size: dp(24)

    MDTextField:
        id: n_name_field
        hint_text: "Name"
        text: ""
        font_size: dp(24)

    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        padding: [0,0,dp(8),dp(24)]
        height: dp(48)
        MDLabel:
            id: "trusted_switch_label"
            text: "Trusted"
            font_style: "H6"

        MDSwitch:
            id: n_trusted
            pos_hint: {"center_y": 0.3}
            active: False

<ConvSettings>
    orientation: "vertical"
    spacing: "16dp"
    size_hint_y: None
    padding: [0, 0, 0, dp(8)]
    height: self.minimum_height

    MDTextField:
        id: dest_field
        hint_text: "Address"
        text: root.context_dest
        # disabled: True
        font_size: dp(18)

    MDTextField:
        id: name_field
        hint_text: "Name"
        text: root.disp_name
        font_size: dp(18)

    MDBoxLayout:
        orientation: "horizontal"
        # spacing: "24dp"
        size_hint_y: None
        padding: [0,0,dp(8),0]
        height: dp(48)
        MDLabel:
            id: trusted_switch_label
            text: "Trusted"
            font_style: "H6"

        MDSwitch:
            id: trusted_switch
            pos_hint: {"center_y": 0.43}
            active: root.trusted

    MDBoxLayout:
        orientation: "horizontal"
        # spacing: "24dp"
        size_hint_y: None
        padding: [0,0,dp(8),0]
        height: dp(48)
        MDLabel:
            id: telemetry_switch_label
            text: "Include Telemetry"
            font_style: "H6"

        MDSwitch:
            id: telemetry_switch
            pos_hint: {"center_y": 0.43}
            active: root.telemetry

<MsgSync>
    orientation: "vertical"
    spacing: "24dp"
    size_hint_y: None
    padding: [0, 0, 0, dp(16)]
    height: self.minimum_height+dp(24)

    MDProgressBar:
        id: sync_progress
        value: 0

    MDLabel:
        id: sync_status
        hint_text: "Name"
        text: "Initiating sync..."


""")
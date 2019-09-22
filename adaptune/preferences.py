#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from collections import OrderedDict, defaultdict
from inspect import getsource
from typing import DefaultDict, Dict, List, Optional, Tuple, Union

import commentjson
from prompt_toolkit import Application, print_formatted_text
from prompt_toolkit.filters import Condition, IsDone
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Container,
    D,
    FormattedTextControl,
    HSplit,
    Layout,
    ScrollOffsets,
    Window,
)
from prompt_toolkit.shortcuts import yes_no_dialog
from prompt_toolkit.styles import pygments_token_to_classname, style_from_pygments_dict
from prompt_toolkit.widgets import Box, TextArea
from pygments.token import Token
from yaspin import yaspin
from yaspin.termcolor import colored

with yaspin(text=colored("Preparing. Wait a minute...", color="cyan", attrs=["bold"])):
    import sounddevice as sd


KeyType = Union[str, int, float]
PathStr = str


global_bindings = KeyBindings()


class InquirerControl(FormattedTextControl):
    selected_index = 0
    answered = False

    def __init__(self, nodes, **kwargs):
        self.nodes = nodes
        super().__init__(self._get_choiced_tokens, **kwargs)

    @property
    def choice_count(self):
        return len(self.nodes)

    def _get_choiced_tokens(self) -> List:
        tokens = []
        T = Token

        def _append(index, label):
            nonlocal self
            selected = index == self.selected_index

            def _select_item(app, mouse_event):
                self.selected_index = index
                self.answered = True

            _ = T.Selected if selected else T
            tokens.append((T.Selected if selected else T, " > " if selected else "   "))
            if selected:
                tokens.append((Token.SetCursorPosition, ""))
            tokens.append(
                (T.Selected if selected else T, "%-24s" % label, _select_item)
            )
            tokens.append((T, "\n"))

        for i, choice in enumerate(self.nodes):
            _append(i, choice)

        tokens.pop()

        return [
            ("class:" + pygments_token_to_classname(x[0]), str(x[1])) for x in tokens
        ]

    def get_selection(self):
        key = self.nodes[self.selected_index]
        return key


class TextBox(Box):
    def __init__(
        self,
        text="",
        multiline=True,
        password=False,
        lexer=None,
        auto_suggest=None,
        completer=None,
        complete_while_typing=True,
        accept_handler=None,
        history=None,
        focusable=True,
        focus_on_click=False,
        wrap_lines=True,
        read_only=False,
        width=None,
        height=None,
        dont_extend_height=False,
        dont_extend_width=False,
        line_numbers=False,
        get_line_prefix=None,
        scrollbar=False,
        style="",
        search_field=None,
        preview_search=True,
        prompt="",
        input_processors=None,
        padding=2,
    ):
        super().__init__(
            TextArea(
                text=text,
                multiline=multiline,
                password=password,
                lexer=lexer,
                auto_suggest=auto_suggest,
                completer=completer,
                complete_while_typing=complete_while_typing,
                accept_handler=accept_handler,
                history=history,
                focusable=focusable,
                focus_on_click=focus_on_click,
                wrap_lines=wrap_lines,
                read_only=read_only,
                width=width,
                height=height,
                dont_extend_height=dont_extend_height,
                dont_extend_width=dont_extend_width,
                line_numbers=line_numbers,
                get_line_prefix=get_line_prefix,
                scrollbar=scrollbar,
                style=style,
                search_field=search_field,
                preview_search=preview_search,
                prompt=prompt,
                input_processors=input_processors,
            ),
            padding=padding,
        )


class PreferenceApp(Application):
    want_to_continue = True
    all_done = False

    breadcrumb = ""
    pref_style = style_from_pygments_dict(
        {
            Token.QuestionMark: "#5F819D",
            Token.Selected: "#FF9D00",
            Token.Instruction: "",
            Token.Answer: "#FF9D00 bold",
            Token.Question: "bold",
            Token.Breadcrumb: "#eeeeee",
        }
    )

    control: InquirerControl
    container: Optional[Container] = None

    confdict: Dict

    attr_header: Dict = {}
    root: List[KeyType] = []

    attributes: Union[Dict, List] = {}
    nodes: List[KeyType] = []

    current_node: KeyType = ""

    kwargs: DefaultDict = defaultdict(OrderedDict)

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.get_config()
        self._initialize()

    def get_config(self):
        self.confdict, _choices = self._load_conf("config.json")
        self.attr_header, self.root = self._load_conf(".attributes.json")

    def set_header(self):
        self.attributes = self.attr_header
        self.nodes = self.root
        self.control = InquirerControl(self.nodes)

    def set_layout(self, additional: Optional[Container] = None):
        elements = [
            Window(
                height=D.exact(1), content=FormattedTextControl(self.get_prompt_tokens)
            )
        ]
        if self.container:
            elements.append(self.container)
        else:
            elements.append(
                ConditionalContainer(
                    Window(
                        self.control,
                        width=D.exact(43),
                        height=D(min=3),
                        scroll_offsets=ScrollOffsets(top=1, bottom=1),
                    ),
                    filter=~IsDone() | ~Condition(lambda: self.all_done),
                )
            )
        if additional:
            elements.append(additional)
        self.layout = Layout(HSplit(elements))

    def setup_bindings(self):
        global global_bindings
        bindings = global_bindings

        @bindings.add("c-q", eager=True)
        @bindings.add("c-c", eager=True)
        def _interrupt(event):
            event.app.exit(None)

        @bindings.add("down", eager=True)
        def move_cursor_down(event):
            self.control.selected_index = (
                self.control.selected_index + 1
            ) % self.control.choice_count

        @bindings.add("up", eager=True)
        def move_cursor_up(event):
            self.control.selected_index = (
                self.control.selected_index - 1
            ) % self.control.choice_count

        @bindings.add("enter", eager=True)
        def set_value(event):
            nonlocal self
            self.control.answered = True
            event.app.invalidate()

        self.key_bindings = bindings

    def _initialize(self):
        self.set_header()
        self.setup_bindings()
        self.set_layout()

        self.kwargs["layout"] = self.layout
        self.kwargs["key_bindings"] = self.key_bindings
        self.kwargs["style"] = self.pref_style
        super().__init__(**self.kwargs)

    def _load_conf(self, configobj: Union[str, Dict, List]) -> Tuple[Dict, List]:
        _config: Dict = {}
        keylist: List = []

        def _eval_values(dictionary: Dict) -> Dict:
            newd: DefaultDict = defaultdict()

            for key, val in dictionary.items():

                if isinstance(val, dict):
                    val = _eval_values(val)  # process recursively
                else:
                    pass

                if key == "type":
                    newd[key] = eval(val)
                else:
                    newd[key] = val

            return newd

        if isinstance(configobj, str):
            with open(
                os.path.join(os.path.dirname(__file__), str(configobj)),
                "r",
                encoding="UTF-8",
            ) as file:
                _config = commentjson.load(file)
        elif isinstance(configobj, dict):
            _config = configobj
        elif isinstance(configobj, list):
            keylist = configobj
        else:
            pass

        config: Dict = _config

        if isinstance(config, dict):
            keylist = list(config.keys())
            keylist = [key for key in keylist if key != "__description__"]
            config = _eval_values(config)

        return config, keylist

    def save_conf(self):
        with open(
            os.path.join(os.path.dirname(__file__), "config.json"),
            "w",
            encoding="UTF-8",
        ) as file:
            commentjson.dump(self.confdict, file, indent=4)

    def get_prompt_tokens(self):
        selected = None
        tokens = []
        tokens.append((Token.QuestionMark, "?"))
        tokens.append((Token.Question, " Configure about: "))

        if self.control:
            selected = self.control.get_selection() if self.control.answered else False
        else:
            selected = self.container.text

        if selected:
            if self.breadcrumb:
                self.breadcrumb += " >"
                tokens.append((Token.Breadcrumb, self.breadcrumb))
            tokens.append((Token.Answer, " " + str(selected)))
            tokens.append((Token, "\n"))
            self.breadcrumb += " " + str(selected)
            self.select_index(selected, self.attributes)
            self.invalidate()
        else:
            if self.breadcrumb:
                tokens.append((Token.Breadcrumb, self.breadcrumb))
            tokens.append((Token.Instruction, " (Use arrow keys)"))

        return [
            ("class:" + pygments_token_to_classname(x[0]), str(x[1])) for x in tokens
        ]

    def select_index(self, key, attributes):
        def set_child_control(key, attributes):
            if isinstance(attributes, dict):
                attr_child = attributes[key]

                if isinstance(attr_child, dict):
                    self.attributes = attr_child
                    self.nodes = list(attr_child.keys())
                elif isinstance(attr_child, list):
                    self.attributes = []
                    self.nodes = attr_child
            else:
                pass

            self.control = InquirerControl(self.nodes)

        def _work_before_node(key, attr):
            nonlocal self
            _result: Union[bool, KeyType] = False

            if isinstance(attr, dict):
                # this branch has some branches
                # special case in "device"
                if key in ["main", "monitor", "input"]:
                    snddevs = list(sd.query_devices())
                    devlist = [devinfo["name"] for devinfo in snddevs]
                    self.current_node = key
                    self.attributes = []
                    self.nodes = devlist

                    self.control = InquirerControl(devlist)
                    self.set_layout(
                        additional=Window(
                            FormattedTextControl(
                                text=to_formatted_text(
                                    sd.query_devices(), auto_convert=True
                                )
                            )
                        )
                    )
                    _result = False

                # other cases
                else:
                    set_child_control(key, attr)
                    self.set_layout()
                    _result = False

            elif isinstance(attr, list):
                if str(self.current_node) in ["main", "monitor", "input"]:
                    pass
                else:
                    self.current_node = key
                self.attributes = []
                _result = key

            return _result

        def _setval_if_key_is_node(key_prev, selected):
            nonlocal self

            # hw_params
            if key_prev in ["rate", "periodsize", "channels"]:
                self.confdict["hw_params"][key_prev] = selected
            elif key_prev in ["alsa", "sounddevice"]:
                self.confdict["hw_params"]["formatname"] = selected

            # filter_params
            elif key_prev == "w":
                self.confdict["filter_params"][key_prev] = selected

            # (as below)
            elif key_prev in ["filter_domain", "filter_algo"]:
                self.confdict[key_prev] = selected

            # devices
            elif key_prev in ["main", "monitor", "input"]:
                self.confdict["devices"][key_prev] = selected

            # [post process]
            self.control.answered = False
            self.all_done = True

            self.reset()
            self.invalidate()
            self.exit(None)

        result = _work_before_node(key, attributes)
        if result:
            key_prev = self.current_node
            _setval_if_key_is_node(key_prev, result)

    def main(self):
        while self.want_to_continue:
            self.run()

            want_to_write = yes_no_dialog(
                title="Preferences",
                text="Do you want to (over)write the configuration file?",
            )
            if want_to_write:
                self.save_conf()

            self.want_to_continue = yes_no_dialog(
                title="Preferences", text="Do you want to configure for other indexes?"
            )
            if self.want_to_continue:
                self._initialize()
                continue

        print_formatted_text("Done!")


if __name__ == "__main__":
    pref_app = PreferenceApp()
    pref_app.main()

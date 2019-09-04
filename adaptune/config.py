import pkgutil
import re
import subprocess
from pygments.token import Token
from prompt_toolkit.styles.pygments import style_from_pygments_dict
from prompt_toolkit.styles import pygments_token_to_classname
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.layout.containers import ScrollOffsets
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import IsDone
from prompt_toolkit.application import Application
from typing import Tuple
import alsaaudio as alsa
from padasip import padasip as pa
import os
import commentjson


with open(
    os.path.join(os.path.dirname(__file__), "params.json"), 'r', encoding='UTF-8'
) as file:
    config = commentjson.load(file)

params = config["params"]
params["formatname"] = eval("alsa." + params["formatname"])

filter_params = config["filter_params"]

domain = config["filter_domain"]

default_filter = eval("pa.filters." + config["filter_algo"])

dev = config["devices"]


def dump_defaults(
    puts: bool = True, description: bool = False
) -> Tuple[str, dict]:
    """
    'params.json' に設定された既定値を出力します。

    Args:
        puts (bool, optional): 標準出力に既定値を出力するかどうか。 デフォルトは True です。
        description (bool, optional): 冒頭の説明文を出力に含めるかどうか。デフォルトは False です。

    Returns:
        Tuple[str, dict]: 文字列型、辞書型の既定値を tuple として返します。
    """
    if description is False:
        del config["__description__"]
    if puts:
        print(commentjson.dumps(config, indent=4))
    return commentjson.dumps(config), config


# [preview] Use 'prompt_toolkit' to config

del config["__description__"]

choices = list(config.keys())
string_query = " Configure about: "
inst = " (Use arrow keys)"


def selected_item(text):
    # res = subprocess.call(text)
    # print(res)
    pass


class InquirerControl(FormattedTextControl):
    selected_option_index = 0
    answered = False

    def __init__(self, choices, **kwargs):
        self.choices = choices
        super(
            InquirerControl,
            self).__init__(
            self._get_choice_tokens,
            **kwargs)

    @property
    def choice_count(self):
        return len(self.choices)

    def _get_choiced_tokens(self):
        tokens = []
        T = Token

        def append(index, label):
            selected = index == self.selected_option_index

            def select_item(app, mouse_event):
                self.selected_option_index = index
                self.answered = True

            _ = T.Selected if selected else T
            tokens.append(
                (T.Selected if selected else T,
                    " > " if selected else "   "))
            if selected:
                tokens.append((Token.SetCursorPosition, ""))
            tokens.append(
                (T.Selected if selected else T, "%-24s" %
                    label, select_item))
            tokens.append((T, "\n"))

        for i, choice in enumerate(self.choices):
            append(i, choice)
        tokens.pop()
        return [
            ("class:" + pygments_token_to_classname(x[0]), str(x[1])) for x in tokens
        ]

    def get_selection(self):
        return self.choices[self.selected_option_index]


ic = InquirerControl(choices)


def get_prompt_tokens():
    tokens = []
    _ = Token
    tokens.append((Token.QuestionMark, "?"))
    tokens.append((Token.Question, string_query))
    if ic.answered:
        tokens.append((Token.Answer, " " + ic.get_selection()))
        selected_item(ic.get_selection())
    else:
        tokens.append((Token.Instruction, inst))
    return [("class:" + pygments_token_to_classname(x[0]), str(x[1]))
            for x in tokens]


HSContainer = HSplit(
    [
        Window(
            height=D.exact(1),
            content=FormattedTextControl(get_prompt_tokens)),
        ConditionalContainer(
            Window(
                ic,
                width=D.exact(43),
                height=D(min=3),
                scroll_offsets=ScrollOffsets(top=1, bottom=1),
            ),
            filter=~IsDone(),
        ),
    ]
)
layout = Layout(HSContainer)


kb = KeyBindings()


@kb.add("c-q", eager=True)
@kb.add("c-c", eager=True)
def _interrupt(event):
    event.app.exit(None)


@kb.add("down", eager=True)
def move_cursor_down(event):
    ic.selected_option_index = (ic.selected_option_index + 1) % ic.choice_count


@kb.add("up", eager=True)
def move_cursor_up(event):
    ic.selected_option_index = (ic.selected_option_index - 1) % ic.choice_count


@kb.add("enter", eager=True)
def set_answer(event):
    ic.answered = True
    event.app.exit(None)


inquirer_style = style_from_pygments_dict(
    {
        Token.QuestionMark: "#5F819D",
        Token.Selected: "#FF9D00",
        Token.Instruction: "",
        Token.Answer: "#FF9D00 bold",
        Token.Question: "bold",
    }
)


app = Application(
    layout=layout, key_bindings=kb, mouse_support=False, style=inquirer_style
)
app.run()


if __name__ == '__main__':
    dump_defaults(description=True)

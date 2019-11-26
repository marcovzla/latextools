import re
from enum import IntEnum
from collections import namedtuple, defaultdict
from string import ascii_letters



Token = namedtuple('Token', 'value code')



class State(IntEnum):
    NewLine = 0
    SkippingSpaces = 1
    MiddleOfLine = 2



class CategoryCode(IntEnum):
    # Escape character; this signals the start of a control sequence.
    # IniTeX makes the backslash \ (code 92) an escape character.
    EscapeCharacter = 0
    # Beginning of group; such a character causes TeX to enter a new level of grouping.
    # The plain format makes the open brace { a beginning-of-group character.
    BeginningOfGroup = 1
    # End of group; TeX closes the current level of grouping.
    # Plain TeX has the closing brace } as end-of-group character.
    EndOfGroup = 2
    # Math shift; this is the opening and closing delimiter for math formulas.
    # Plain TeX uses the dollar sign $ for this.
    MathShift = 3
    # Alignment tab; the column (row) separator in tables made with \halign (\valign).
    # In plain TeX this is the ampersand &.
    AlignmentTab = 4
    # End of line; a character that TeX considers to signal the end of an input line.
    # IniTeX assigns this code to the <return>, that is, code 13.
    EndOfLine = 5
    # Parameter character; this indicates parameters for macros.
    # In plain TeX this is the hash sign.
    ParameterCharacter = 6
    # Superscript; this precedes superscript expressions in math mode.
    # It is also used to denote character codes that cannot be entered in an input file.
    # In plain TeX this is the circumflex ^.
    Superscript = 7
    # Subscript; this precedes subscript expressions in math mode.
    # In plain TeX the underscore _ is used for this.
    Subscript = 8
    # Ignored; characters of this category are removed from the input, and have therefore no influence on further TeX processing.
    # In plain TeX this is the <null> character, that is, code 0.
    Ignored = 9
    # Space; space characters receive special treatment.
    # IniTeX assigns this category to the ASCII <space> character, code 32.
    Space = 10
    # Letter; in IniTeX only the characters a..z, A..Z are in this category.
    # Often, macro packages make some ‘secret’ character (for instance @) into a letter.
    Letter = 11
    # Other; IniTeX puts everything that is not in the other categories into this category.
    # Thus it includes, for instance, digits and punctuation.
    Other = 12
    # Active; active characters function as a TeX command, without being preceded by an escape character.
    # In plain TeX this is only the tie character ~ , which is defined to produce an unbreakable space
    Active = 13
    # Comment character; from a comment character onwards, TeX considers the rest of an input line to be comment and ignores it.
    # In IniTeX the percent sign % is made a comment character.
    Comment = 14
    # Invalid character; this category is for characters that should not appear in the input.
    # IniTeX assigns the ASCII <delete> character, code 127, to this category.
    Invalid = 15

    ControlSequence = 16
    ParameterToken = 17



class Tokenizer:

    def __init__(self, text=None, endlinechar=13):
        # caracters not registered in catcodes get a code 12 (Other)
        self.catcodes = defaultdict(lambda: CategoryCode.Other)
        # register defaults
        self.catcodes.update({
            '\\':   CategoryCode.EscapeCharacter,
            '{' :   CategoryCode.BeginningOfGroup,
            '}' :   CategoryCode.EndOfGroup,
            '$' :   CategoryCode.MathShift,
            '&' :   CategoryCode.AlignmentTab,
            '\r':   CategoryCode.EndOfLine,
            '#' :   CategoryCode.ParameterCharacter,
            '^' :   CategoryCode.Superscript,
            '_' :   CategoryCode.Subscript,
            '\0':   CategoryCode.Ignored,
            ' ' :   CategoryCode.Space,
            '\t':   CategoryCode.Space,
            '~' :   CategoryCode.Active,
            '%' :   CategoryCode.Comment,
            '\x7f': CategoryCode.Invalid,
        })
        # register ascii letters
        for c in ascii_letters:
            self.catcodes[c] = CategoryCode.Letter
        # set default endlinechar
        self.set_endlinechar(endlinechar)
        # reset tokenizer
        self.reset(text)

    def __iter__(self):
        while self.has_token():
            yield self.get_token()

    def reset(self, text=None):
        """Resets the tokenizer with optional new input text."""
        self.state = State.NewLine
        self.currline = 0
        self.currchar = 0
        self.next_token = None
        if text is not None:
            self.text = text.strip()
            self.lines = list(self.lines())

    def set_endlinechar(self, char):
        if isinstance(char, str) and len(char) == 1 and 0 <= ord(char) < 255:
            self.endlinechar = char
        elif isinstance(char, int) and 0 <= char < 255:
            self.endlinechar = chr(char)
        else:
            self.endlinechar = None

    def lines(self):
        if self.text is not None:
            for line in self.text.splitlines():
                line = line.rstrip()
                if self.endlinechar is not None:
                    line += self.endlinechar
                yield line

    def peek(self):
        if self.next_token is None:
            self.next_token = self.make_token()
        return self.next_token

    def has_token(self):
        return self.peek() is not None

    def get_token(self):
        if self.next_token is None:
            token = self.make_token()
        else:
            token = self.next_token
            self.next_token = None
        return token

    def make_token(self):
        while self.currline < len(self.lines):
            # get current line
            line = self.lines[self.currline]
            while self.currchar < len(line):
                # get current char
                char = line[self.currchar]
                code = self.catcodes[char]
                self.currchar += 1
                # start a token
                token = char
                if code == CategoryCode.EscapeCharacter:
                    char = line[self.currchar]
                    code = self.catcodes[char]
                    self.currchar += 1
                    if code == CategoryCode.Letter:
                        # control word
                        self.state = State.SkippingSpaces
                        token += char
                        while self.currchar < len(line):
                            char = line[self.currchar]
                            code = self.catcodes[char]
                            if code == CategoryCode.Letter:
                                token += char
                                self.currchar += 1
                            else:
                                break
                    elif code == CategoryCode.Space:
                        # control space
                        self.state = State.SkippingSpaces
                        token += char
                    else:
                        # control symbol
                        self.state = State.MiddleOfLine
                        token += char
                    return Token(token, CategoryCode.ControlSequence)
                elif code == CategoryCode.EndOfLine:
                    # skip rest of current line
                    self.currline += 1
                    self.currchar = 0
                    # remember state
                    prev_state = self.state
                    # transition to new state
                    self.state = State.NewLine
                    if prev_state == State.NewLine:
                        return Token('\\par', CategoryCode.ControlSequence)
                    elif prev_state == State.SkippingSpaces:
                        break
                    elif prev_state == State.MiddleOfLine:
                        return Token(' ', CategoryCode.Space)
                elif code == CategoryCode.ParameterCharacter:
                    if self.currchar < len(line):
                        char = line[self.currchar]
                        if char.isdigit():
                            # build a parameter token
                            token += char
                            code = CategoryCode.ParameterToken
                            self.currchar += 1
                        elif self.catcodes[char] == CategoryCode.ParameterCharacter:
                            # ignore second parameter char
                            self.currchar += 1
                    self.state = State.MiddleOfLine
                    return Token(token, code)
                elif code == CategoryCode.Superscript:
                    self.state = State.MiddleOfLine
                    chars = line[self.currchar:self.currchar+3]
                    if len(chars) > 1 and self.catcodes[chars[0]] == CategoryCode.Superscript:
                        enc = chars[1:]
                        if re.match(r'[0-9a-f][0-9a-f]', enc):
                            n = int(enc, 16)
                            if 0 <= n < 256:
                                token = chr(n)
                                code = self.catcodes[token]
                                self.currchar += 3
                                return Token(token, code)
                            n = ord(enc[0])
                            if 0 <= n < 128:
                                token = chr((n + 64) % 128)
                                code = self.catcodes[token]
                                self.currchar += 2
                                return Token(token, code)
                    return Token(token, code)
                elif code == CategoryCode.Ignored:
                    pass
                elif code == CategoryCode.Space:
                    if self.state == State.MiddleOfLine:
                        self.state = State.SkippingSpaces
                        return Token(' ', CategoryCode.Space)
                elif code == CategoryCode.Comment:
                    # skip rest of current line
                    self.currline += 1
                    self.currchar = 0
                    break
                elif code == CategoryCode.Invalid:
                    raise Exception('invalid character')
                else:
                    self.state = State.MiddleOfLine
                    return Token(token, code)

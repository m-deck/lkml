import logging
from typing import List, Sequence, Type, Optional
import lkml.tokens as tokens

logger = logging.getLogger(f"{__name__}.parser")

"""

LookML grammar
---
expression = (block / pair / list)*

block = key literal? "{" expression "}"

pair = key value

list = key literal? "[" csv "]"

csv = (literal / quoted_literal) ("," (literal / quoted_literal))*

value = quoted_literal / (literal sql_block_end?)

sql_block_end = ;;

key = literal ":"

quoted_literal = '"' [^\"]+ '"'

literal = [0-9A-Za-z_]+

"""


class Parser:
    def __init__(self, stream: Sequence[tokens.Token]):
        for token in stream:
            if not isinstance(token, tokens.Token):
                raise TypeError(
                    f"Type {type(token)} for {token} is not a valid token type."
                )
        self.tokens = stream
        logger.debug(tokens)
        self.index = 0
        self.mark: int = None

    def set_mark(self):
        self.mark = self.index

    def jump_to_mark(self):
        self.index = self.mark

    def backtrack_if_none(method):
        def wrapper(self, *args, **kwargs):
            self.set_mark()
            result = method(self, *args, **kwargs)
            if result is None:
                self.jump_to_mark()
            return result

        return wrapper

    def peek(self, length: int = 1):
        if length > 1:
            return self.tokens[self.index : self.index + length]
        else:
            return self.tokens[self.index]

    def advance(self, length: int = 1):
        logger.debug("\t" + str(self.tokens[self.index]))
        self.index += length

    def consume(self):
        token = self.peek()
        self.advance()
        return token

    def consume_token_value(self):
        token = self.consume()
        return token.value

    def check(self, *token_types: Type[tokens.Token]):
        logger.debug(f"Checking {self.peek()} against {token_types}")
        for token_type in token_types:
            if not issubclass(token_type, tokens.Token):
                raise TypeError(f"{token_type} is not a valid token type.")
        if type(self.peek()) in token_types:
            return True
        else:
            return False

    def parse(self) -> List:
        return self.parse_expression()

    @backtrack_if_none
    def parse_expression(self) -> List:
        """expression = (block / pair / list)*"""
        logger.debug("Entering expression parser")
        expression = []
        if self.check(tokens.StreamStartToken):
            self.advance()
        while not self.check(tokens.StreamEndToken, tokens.BlockEndToken):
            block = self.parse_block()
            if block is not None:
                expression.append(block)
                continue

            pair = self.parse_pair()
            if pair is not None:
                expression.append(pair)
                continue

            list = self.parse_list()
            if list is not None:
                expression.append(list)
                continue

            raise Exception("Syntax error.")

        logger.debug(f"Returning {expression} from expression parser")
        return expression

    @backtrack_if_none
    def parse_block(self) -> Optional[dict]:
        """key literal? '{' expression '}'"""
        logger.debug("Entering block parser")

        key = self.parse_key()
        if key is None:
            return key

        if self.check(tokens.LiteralToken):
            literal = self.consume_token_value()

        if self.check(tokens.BlockStartToken):
            self.advance()
        else:
            return None

        expression = self.parse_expression()
        if expression is None:
            return expression

        if self.check(tokens.BlockEndToken):
            self.advance()
        else:
            return None

        block = {key: {"expression": expression}}
        if literal:
            block[key]["name"] = literal

        logger.debug(f"Returning {block} from block parser")
        return block

    @backtrack_if_none
    def parse_pair(self) -> Optional[dict]:
        """pair = key value"""
        logger.debug("Entering pair parser")

        key = self.parse_key()
        if key is None:
            return key

        value = self.parse_value()
        if value is None:
            return value

        pair = {key: value}
        logger.debug(f"Returning {pair} from pair parser")
        return pair

    @backtrack_if_none
    def parse_key(self) -> Optional[str]:
        """key = literal ':'"""
        if self.check(tokens.LiteralToken):
            value = self.consume_token_value()
        else:
            return None

        if self.check(tokens.ValueToken):
            self.advance()
        else:
            return None

        return value

    @backtrack_if_none
    def parse_value(self) -> Optional[str]:
        """value = quoted_literal / (literal sql_block_end?)"""
        logger.debug("Entering value parser")
        if self.check(tokens.QuotedLiteralToken):
            value = self.consume_token_value()
            logger.debug(f"Returning {value} from expression parser")
            return value
        elif self.check(tokens.LiteralToken):
            value = self.consume_token_value()
            if self.check(tokens.SqlEndToken):
                self.advance()
            logger.debug(f"Returning {value} from expression parser")
            return value
        else:
            return None

    @backtrack_if_none
    def parse_list(self) -> Optional[dict]:
        """list = key literal? '[' csv ']'"""
        logger.debug("Entering list parser")

        key = self.parse_key()
        if key is None:
            return key

        if self.check(tokens.LiteralToken):
            literal = self.consume_token_value()

        if self.check(tokens.ListStartToken):
            self.advance()
        else:
            return None

        csv = self.parse_csv()
        if csv is None:
            return csv

        if self.check(tokens.ListEndToken):
            self.advance()
            # TODO: Return key name as well
            list = {key: csv}
            logger.debug(f"Returning {list} from list parser")
            return list
        else:
            return None

    @backtrack_if_none
    def parse_csv(self) -> Optional[list]:
        """csv = (literal / quoted_literal) ("," (literal / quoted_literal))*"""
        logger.debug("Entering comma-separated value parser")
        values = []

        if self.check(tokens.LiteralToken):
            values.append(self.consume_token_value())
        elif self.check(tokens.QuotedLiteralToken):
            values.append(self.consume_token_value())
        else:
            return None

        while not self.check(tokens.ListEndToken):
            if self.check(tokens.CommaToken):
                self.advance()
            else:
                return None

            if self.check(tokens.LiteralToken):
                values.append(self.consume_token_value())
            elif self.check(tokens.QuotedLiteralToken):
                values.append(self.consume_token_value())
            else:
                return None

        logger.debug(f"Returning {values} from csv parser")
        return values

# -*- coding: utf8 -*-

"""
Input and Output
"""

import re

from mathics.builtin.base import Builtin, Predefined, BinaryOperator, BoxConstruct, BoxConstructError, Operator
from mathics.builtin.tensors import get_dimensions
from mathics.builtin.comparison import expr_min
from mathics.builtin.lists import list_boxes
from mathics.builtin.options import options_to_rules
from mathics.core.expression import Expression, String, Symbol, Integer, Rational, Real, Complex, BoxError

MULTI_NEWLINE_RE = re.compile(r"\n{2,}")

class Format(Builtin):
    """
    Assign values to 'Format' to control how particular expressions should be formatted when printed
    to the user.
    >> Format[f[x___]] := Infix[{x}, "~"]
    >> f[1, 2, 3]
     = 1 ~ 2 ~ 3
    >> f[1]
     = 1
     
    Raw objects cannot be formatted: 
    >> Format[3] = "three";
     : Cannot assign to raw object 3.
    
    Format types must be symbols:
    >> Format[r, a + b] = "r";
     : Format type a + b is not a symbol.
     
    Formats must be attached to the head of an expression:
    >> f /: Format[g[f]] = "my f";
     : Tag f not found or too deep for an assigned rule.
    """
    
    messages = {
        'fttp': "Format type `1` is not a symbol.",
    }
    
def parenthesize(precedence, leaf, leaf_boxes, when_equal):
    from mathics.builtin import builtins_precedence
    
    while leaf.has_form('HoldForm', 1):
        leaf = leaf.leaves[0]
    if leaf.has_form(('Infix', 'Prefix', 'Postfix'), 3, None):
        leaf_prec = leaf.leaves[2].get_int_value()
    elif leaf.has_form('PrecedenceForm', 2):
        leaf_prec = leaf.leaves[1].get_int_value()
    else:
        leaf_prec = builtins_precedence.get(leaf.get_head_name())
    if precedence is not None and leaf_prec is not None:
        if precedence > leaf_prec or (precedence == leaf_prec and when_equal):
            return Expression('RowBox', Expression('List', String("("), leaf_boxes, String(")")))
    return leaf_boxes

def make_boxes_infix(leaves, ops, precedence, grouping, form):
    
    result = []
    for index, leaf in enumerate(leaves):
        if index > 0:
            result.append(ops[index - 1])
        parenthesized = False
        if grouping == 'NonAssociative':
            parenthesized = True
        elif grouping == 'Left' and index > 0:
            parenthesized = True
        elif grouping == 'Right' and index == 0:
            parenthesized = True
            
        leaf_boxes = MakeBoxes(leaf, form)
        leaf = parenthesize(precedence, leaf, leaf_boxes, parenthesized) 
        result.append(leaf)
    return Expression('RowBox', Expression('List', *result))
    
class MakeBoxes(Builtin):
    attributes = ('HoldAllComplete',)
    
    rules = {
        'MakeBoxes[Infix[head_[leaves___]], f:StandardForm|TraditionalForm|OutputForm|InputForm]': 'MakeBoxes[Infix[head[leaves], StringForm["~`1`~", head]], f]',
        'MakeBoxes[expr_]': 'MakeBoxes[expr, StandardForm]',
        'MakeBoxes[(form:StandardForm|TraditionalForm|OutputForm|TeXForm|MathMLForm)[expr_], StandardForm|TraditionalForm]':
            'MakeBoxes[expr, form]',
        'MakeBoxes[(form:OutputForm|MathMLForm|TeXForm)[expr_], OutputForm]':
            'MakeBoxes[expr, form]',    
        'MakeBoxes[StandardForm[expr_], OutputForm]':
            'MakeBoxes[expr, OutputForm]',        
        'MakeBoxes[FullForm[expr_], StandardForm|TraditionalForm|OutputForm]':
            'StyleBox[MakeBoxes[expr, FullForm], ShowStringCharacters->True]',
        'MakeBoxes[InputForm[expr_], StandardForm|TraditionalForm|OutputForm]':
            'StyleBox[MakeBoxes[expr, InputForm], ShowStringCharacters->True]',
        'MakeBoxes[PrecedenceForm[expr_, prec_], f_]': 'MakeBoxes[expr, f]',
        'MakeBoxes[Style[expr_, OptionsPattern[Style]], f_]': 'StyleBox[MakeBoxes[expr, f], ImageSizeMultipliers->OptionValue[ImageSizeMultipliers]]',
    }
    
    def apply_general(self, expr, f, evaluation):
        'MakeBoxes[expr_, f:TraditionalForm|StandardForm|OutputForm|InputForm|FullForm]'
        
        if expr.is_atom():
            x = expr
            if isinstance(x, Symbol):
                return String(x.name)
            elif isinstance(x, String):
                return String('"' + x.value + '"')
            elif isinstance(x, (Integer, Real)):
                return x.make_boxes(f.get_name())
            elif isinstance(x, (Rational, Complex)):
                return x.format(evaluation, f.get_name())
        else:
            head = expr.head
            leaves = expr.leaves
            
            f_name = f.get_name()
            if f_name == 'TraditionalForm':
                left, right = '(', ')'
            else:
                left, right = '[', ']'
            result = [MakeBoxes(head, f), String(left)]
            if len(leaves) > 1:
                row = []
                if f_name in ('InputForm', 'OutputForm', 'FullForm'):
                    sep = ', '
                else:
                    sep = ','
                for index, leaf in enumerate(leaves):
                    if index > 0:
                        row.append(String(sep))
                    row.append(MakeBoxes(leaf, f))
                result.append(RowBox(Expression('List', *row)))
            elif len(leaves) == 1:
                result.append(MakeBoxes(leaves[0], f))
            result.append(String(right))
            return RowBox(Expression('List', *result))
    
    def _apply_atom(self, x, f, evaluation):
        'MakeBoxes[x_?AtomQ, f:TraditionalForm|StandardForm|OutputForm|InputForm|FullForm]'
        
        if isinstance(x, Symbol):
            return String(x.name)
        elif isinstance(x, String):
            return String('"' + x.value + '"')
        elif isinstance(x, (Integer, Real)):
            return x.make_boxes(f.get_name())
        elif isinstance(x, (Rational, Complex)):
            return x.format(evaluation, f.get_name())
    
    def apply_outerprecedenceform(self, expr, prec, f, evaluation):
        'MakeBoxes[OuterPrecedenceForm[expr_, prec_], f:StandardForm|TraditionalForm|OutputForm|InputForm]'
        
        precedence = prec.get_int_value()
        boxes = MakeBoxes(expr)
        return parenthesize(precedence, expr, boxes, True)
    
    def apply_postprefix(self, p, expr, h, prec, f, evaluation):
        'MakeBoxes[(p:Prefix|Postfix)[expr_, h_, prec_:None], f:StandardForm|TraditionalForm|OutputForm|InputForm]'
        
        if not isinstance(h, String):
            h = MakeBoxes(h, f)
        
        precedence = prec.get_int_value()

        leaves = expr.get_leaves()
        if len(leaves) == 1:    
            leaf = leaves[0]
            leaf_boxes = MakeBoxes(leaf, f)
            leaf = parenthesize(precedence, leaf, leaf_boxes, True)
            if p.get_name() == 'Postfix':
                args = (leaf, h)
            else:
                args = (h, leaf)
                
            return Expression('RowBox', Expression('List', *args))
        else:
            return MakeBoxes(expr, f)
    
    def apply_infix(self, expr, h, prec, grouping, f, evaluation):
        'MakeBoxes[Infix[expr_, h_, prec_:None, grouping_:None], f:StandardForm|TraditionalForm|OutputForm|InputForm]'
        
        def get_op(op):
            if not isinstance(op, String):
                op = MakeBoxes(op, f)
            else:
                op_value = op.get_string_value()
                if f.get_name() == 'InputForm' and op_value == '*':
                    pass
                elif f.get_name() in ('InputForm', 'OutputForm') and not op_value.startswith(' ') and not op_value.endswith(' '):
                    op = String(' ' + op_value + ' ')
            return op
        
        precedence = prec.get_int_value()
        grouping = grouping.get_name()
        
        leaves = expr.get_leaves()
        if len(leaves) > 1:
            if h.has_form('List', len(leaves) - 1):
                ops = [get_op(op) for op in h.leaves]
            else:
                ops = [get_op(h)] * (len(leaves) - 1)
            return make_boxes_infix(leaves, ops, precedence, grouping, f)
        elif len(leaves) == 1:
            return MakeBoxes(leaves[0], f)
        else:
            return MakeBoxes(expr, f)
        
class ToBoxes(Builtin):
    """
    >> ToBoxes[a + b]
     = RowBox[{a, +, b}]
    >> ToBoxes[a ^ b] // FullForm
     = SuperscriptBox["a", "b"]
    """
    
    def apply(self, expr, form, evaluation):
        'ToBoxes[expr_, form_:StandardForm]'
        
        form_name = form.get_name()
        if form_name is None:
            evaluation.message('ToBoxes', 'boxfmt', form)
        boxes = expr.format(evaluation, form_name)
        return boxes
    
class RowBox(Builtin):
    pass

class Row(Builtin):    
    def apply_makeboxes(self, items, sep, f, evaluation):
        'MakeBoxes[Row[{items___}, sep_:""], f:StandardForm|TraditionalForm|OutputForm]'
        
        items = items.get_sequence()
        if not isinstance(sep, String):
            sep = MakeBoxes(sep, f)
        if len(items) == 1:
            return MakeBoxes(items[0], f)
        else:
            result = []
            for index, item in enumerate(items):
                if index > 0 and not sep.same(String('')):
                    result.append(sep)
                result.append(MakeBoxes(item, f))
            return RowBox(Expression('List', *result))

def is_constant(list):
    if list:
        return all(item == list[0] for item in list[1:])
    return True

class GridBox(BoxConstruct):
    """
    #> Grid[{{a,bc},{d,e}}, ColumnAlignments:>Symbol["Rig"<>"ht"]]
     = a   bc
     . 
     . d   e
    """
      
    options = {
        'ColumnAlignments': 'Center',
    }
    
    def get_array(self, leaves, evaluation):
        options = self.get_option_values(leaves[1:], evaluation)
        if not leaves:
            raise BoxConstructError
        expr = leaves[0]
        if not expr.has_form('List', None):
            if not all(leaf.has_form('List', None) for leaf in expr.leaves):
                raise BoxConstructError
        items = [leaf.leaves for leaf in expr.leaves]
        if not is_constant([len(row) for row in items]):
            raise BoxConstructError
        return items, options
    
    def boxes_to_tex(self, leaves, **box_options):
        evaluation = box_options.get('evaluation')
        items, options = self.get_array(leaves, evaluation)
        new_box_options = box_options.copy()
        new_box_options['inside_list'] = True
        column_alignments = options['ColumnAlignments'].get_name()
        if column_alignments in ('Center', 'Left', 'Right'):
            column_alignments = column_alignments[0].lower()
        else:
            raise BoxConstructError
        column_count = 0
        for row in items:
            column_count = max(column_count, len(row))
        result = r'\begin{array}{%s}' % (column_alignments * column_count) + ' '
        for index, row in enumerate(items):
            result += ' & '.join(item.boxes_to_tex(**new_box_options) for item in row)
            if index != len(items) - 1:
                result += '\\\\ '
        result += r'\end{array}'
        return result
    
    def boxes_to_xml(self, leaves, **box_options):
        evaluation = box_options.get('evaluation')
        items, options = self.get_array(leaves, evaluation)
        attrs = {}
        column_alignments = options['ColumnAlignments'].get_name()
        if column_alignments in ('Center', 'Left', 'Right'):
            attrs['columnalign'] = column_alignments.lower()
        else:
            raise BoxConstructError
        attrs = ' ' + ' '.join('%s="%s"' % (name, value) for name, value in attrs.iteritems())
        result = '<mtable%s>\n' % attrs
        new_box_options = box_options.copy()
        new_box_options['inside_list'] = True
        for row in items:
            result += '<mtr>'
            for item in row:
                result += '<mtd%s>%s</mtd>' % (attrs, item.boxes_to_xml(**new_box_options))
            result += '</mtr>\n'
        result += '</mtable>'
        return result
    
    def boxes_to_text(self, leaves, **box_options):
        evaluation = box_options.get('evaluation')
        items, options = self.get_array(leaves, evaluation)
        result = ''
        if not items:
            return ''
        widths = [0] * len(items[0])
        cells = [[item.boxes_to_text(**box_options).splitlines() for item in row] for row in items]
        for row in cells:
            for index, cell in enumerate(row):
                if index >= len(widths):
                    raise BoxConstructError
                for line in cell:
                    widths[index] = max(widths[index], len(line))
        for row_index, row in enumerate(cells):
            if row_index > 0:
                result += '\n'
            k = 0
            while True:
                line_exists = False
                line = ''
                for cell_index, cell in enumerate(row):
                    if len(cell) > k:
                        line_exists = True
                        text = cell[k]
                    else:
                        text = ''
                    line += text
                    if cell_index < len(row) - 1:
                        line += ' ' * (widths[cell_index] - len(text))
                        #if cell_index < len(row) - 1:
                        line += '   '
                if line_exists:
                    result += line + '\n'
                else:
                    break
                k += 1
        return result
    
class Grid(Builtin):
    """
    >> Grid[{{a, b}, {c, d}}]
     = a   b
     .
     . c   d
    """
    
    options = GridBox.options
      
    def apply_makeboxes(self, array, f, evaluation, options):
        'MakeBoxes[Grid[array_?MatrixQ, OptionsPattern[Grid]], f:StandardForm|TraditionalForm|OutputForm]'
        
        array = Expression('List', *(Expression('List', *(Expression('MakeBoxes', item, f)
            for item in row.leaves)) for row in array.leaves))
        
        return Expression('GridBox', array, *options_to_rules(options))
    
class TableForm(Builtin):
    """
    >> TableForm[Array[a, {3,2}],TableDepth->1]
     = {a[1, 1], a[1, 2]}
     . 
     . {a[2, 1], a[2, 2]}
     . 
     . {a[3, 1], a[3, 2]}
     
    A table of Graphics:
    >> Table[Style[Graphics[{EdgeForm[{Black}], RGBColor[r,g,b], Rectangle[]}], ImageSizeMultipliers->{0.2, 1}], {r,0,1,1/2}, {g,0,1,1/2}, {b,0,1,1/2}] // TableForm
     = -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
     . 
     . -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
     . 
     . -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
     .                                     
     . -Graphics-   -Graphics-   -Graphics-
    """
    
    options = {
        'TableDepth': 'Infinity',
    }
    
    def apply_makeboxes(self, table, f, evaluation, options):
        'MakeBoxes[%(name)s[table_, OptionsPattern[%(name)s]], f:StandardForm|TraditionalForm|OutputForm]'
        
        dims = len(get_dimensions(table, head=Symbol('List')))
        depth = self.get_option(options, 'TableDepth', evaluation).unformatted
        depth = expr_min((Integer(dims), depth))
        depth = depth.get_int_value()
        if depth is None:
            evaluation.message(self.get_name(), 'int')
            return
            
        if depth <= 0:
            return Expression('MakeBoxes', table, f)
        elif depth == 1:
            return Expression('GridBox', Expression('List', *(Expression('List',
                Expression('MakeBoxes', item, f)) for item in table.leaves)))
        else:
            new_depth = Expression('Rule', Symbol('TableDepth'), depth-2)
            
            def transform_item(item):
                if depth > 2:
                    return Expression(self.get_name(), item, new_depth)
                else:
                    return item
                
            return Expression('GridBox', Expression('List', *(Expression('List',
                *(Expression('MakeBoxes', transform_item(item), f)
                    for item in row.leaves)) for row in table.leaves)))
    
class MatrixForm(TableForm):
    """
    >> Array[a,{4,3}]//MatrixForm
     = a[1, 1]   a[1, 2]   a[1, 3]
     . 
     . a[2, 1]   a[2, 2]   a[2, 3]
     . 
     . a[3, 1]   a[3, 2]   a[3, 3]
     . 
     . a[4, 1]   a[4, 2]   a[4, 3]
    """
    
    def apply_makeboxes_matrix(self, table, f, evaluation, options):
        'MakeBoxes[%(name)s[table_, OptionsPattern[%(name)s]], f:StandardForm|TraditionalForm]'
        
        result = super(MatrixForm, self).apply_makeboxes(table, f, evaluation, options)
        if result.get_head_name() == 'GridBox':
            return Expression('RowBox', Expression('List', String("("), result, String(")")))
        return result

class Superscript(Builtin):
    """
    >> Superscript[x,3] // TeXForm
     = x^3
    """
    
    rules = {
        'MakeBoxes[Superscript[x_, y_], f:StandardForm|TraditionalForm]': 'SuperscriptBox[MakeBoxes[x, f], MakeBoxes[y, f]]',
    }

class Subscript(Builtin):
    """
    >> Subscript[x,1,2,3] // TeXForm
     = x_{1,2,3}
    """
    
    def apply_makeboxes(self, x, y, f, evaluation):
        'MakeBoxes[Subscript[x_, y__], f:StandardForm|TraditionalForm]'
        
        y = y.get_sequence()
        return Expression('SubscriptBox', Expression('MakeBoxes', x, f), *list_boxes(y, f))
    
class Subsuperscript(Builtin):
    """
    >> Subsuperscript[a, b, c] // TeXForm
     = a_b^c
    """
    
    rules = {
        'MakeBoxes[Subsuperscript[x_, y_, z_], f:StandardForm|TraditionalForm]': 'SubsuperscriptBox[MakeBoxes[x, f], MakeBoxes[y, f], MakeBoxes[z, f]]',
    }
    
class Postfix(BinaryOperator):
    """
    >> b // a
     = a[b]
    >> c // b // a
     = a[b[c]]
     
    The postfix operator '//' is parsed to an expression before evaluation: 
    >> Hold[x // a // b // c // d // e // f]
     = Hold[f[e[d[c[b[a[x]]]]]]]
    """
    
    operator = '//'
    operator_display = None
    precedence = 70
    grouping = 'Left'
    
    def post_parse(self, expression):
        #print expression
        return Expression(expression.leaves[1].post_parse(), expression.leaves[0].post_parse())
    
class Prefix(BinaryOperator):
    """
    >> a @ b
     = a[b]
    >> a @ b @ c
     = a[b[c]]
    >> Format[p[x_]] := Prefix[{x}, "*"]
    >> p[3]
     = *3
    >> Format[q[x_]] := Prefix[{x}, "~", 350]
    >> q[a+b]
     = ~(a + b)
    >> q[a*b]
     = ~a b
    >> q[a]+b
     = b + ~a
     
    The prefix operator '@' is parsed to an expression before evaluation:
    >> Hold[a @ b @ c @ d @ e @ f @ x]
     = Hold[a[b[c[d[e[f[x]]]]]]]
    """
    
    operator = '@'
    operator_display = None
    precedence = 640
    grouping = 'Right'
    
    def post_parse(self, expression):
        return Expression(expression.leaves[0].post_parse(), expression.leaves[1].post_parse())
    
class Infix(Builtin):
    """
    >> Format[g[x_, y_]] := Infix[{x, y}, "#", 350, Left]
    >> g[a, g[b, c]]
     = a # (b # c)
    >> g[g[a, b], c]
     = a # b # c
    >> g[a + b, c]
     = (a + b) # c
    >> g[a * b, c]
     = a b # c
    >> g[a, b] + c
     = c + a # b 
    >> g[a, b] * c
     = c (a # b)
     
    >> Infix[{a, b, c}, {"+", "-"}]
     = a + b - c
     
    #> Format[r[items___]] := Infix[If[Length[{items}] > 1, {items}, {ab}], "~"]
    #> r[1, 2, 3]
     = 1 ~ 2 ~ 3
    #> r[1]
     = ab
    """
    
class StringForm(Builtin):
    """
    >> StringForm["`1` bla `2` blub `` bla `2`", a, b, c]
     = a bla b blub c bla b
    """
    
    format_re = re.compile(r'(\`(\d*)\`)')
    
    def apply_makeboxes(self, s, args, f, evaluation):
        'MakeBoxes[StringForm[s_String, args___], f:StandardForm|TraditionalForm|OutputForm]'
        
        s = s.value
        args = args.get_sequence()
        result = []
        pos = 0
        last_index = 0
        for match in self.format_re.finditer(s):
            start, end = match.span(1)
            if match.group(2):
                index = int(match.group(2))
            else:
                index = last_index + 1
            if index > last_index:
                last_index = index
            if start > pos:
                result.append(String(s[pos:start]))
            pos = end
            if 1 <= index <= len(args):
                arg = args[index - 1]
                result.append(MakeBoxes(arg, f))
        if pos < len(s):
            result.append(String(s[pos:]))
        return RowBox(Expression('List', *result))

class Message(Builtin):
    """
    >> a::b = "Hello world!"
     = Hello world!
    >> Message[a::b]
     : Hello world!
    >> a::c := "Hello `1`, Mr 00`2`!"
    >> Message[a::c, "you", 3 + 4]
     : Hello you, Mr 007!
    """
    
    attributes = ('HoldFirst',)
    
    def apply(self, symbol, tag, params, evaluation):
        'Message[MessageName[symbol_Symbol, tag_String], params___]'
        
        params = params.get_sequence()
        evaluation.message(symbol.name, tag.value, *params)
        return Symbol('Null')
    
class Quiet(Builtin):
    """
    <dl>
    <dt>'Quiet[$expr$, {$s1::t1$, ...}]'
        <dd>evaluates $expr$, without messages '{$s1::t1$, ...}' being displayed.
    <dt>'Quiet[$expr$, All]'
        <dd>evaluates $expr$, without any messages being displayed.
    <dt>'Quiet[$expr$, None]'
        <dd>evaluates $expr$, without all messages being displayed.
    <dt>'Quiet[$expr$, $off$, $on$]'
        <dd>evaluates $expr$, with messages $off$ being suppressed, but messages $on$ being displayed.
    </dl>
    
    >> a::b = "Hello";
    >> Quiet[x+x, {a::b}]
     = 2 x
    >> Quiet[Message[a::b]; x+x, {a::b}]
     = 2 x
     
    >> Message[a::b]; y=Quiet[Message[a::b]; x+x, {a::b}]; Message[a::b]; y
     : Hello
     : Hello
     = 2 x
     
    >> Quiet[expr, All, All]
     : Arguments 2 and 3 of Quiet[expr, All, All] should not both be All.
     = Quiet[expr, All, All]
    >> Quiet[x + x, {a::b}, {a::b}]
     : In Quiet[x + x, {a::b}, {a::b}] the message name(s) {a::b} appear in both the list of messages to switch off and the list of messages to switch on.
     = Quiet[x + x, {a::b}, {a::b}]
    """
    
    attributes = ('HoldAll',)
    
    messages = {
        'anmlist': "Argument `1` of `2` should be All, None, a message name, or a list of message names.",
        'allall': "Arguments 2 and 3 of `1` should not both be All.",
        'conflict': "In `1` the message name(s) `2` appear in both the list of messages to switch off and the list of messages to switch on.",
    }
    
    rules = {
        'Quiet[expr_]': 'Quiet[expr, All]',
        'Quiet[expr_, moff_]': 'Quiet[expr, moff, None]',
    }
    
    def apply(self, expr, moff, mon, evaluation):
        'Quiet[expr_, moff_, mon_]'
        
        def get_msg_list(expr):
            if expr.has_form('MessageName', 2):
                expr = Expression('List', expr)
            if expr.get_name() == 'All':
                all = True
                messages = []
            elif expr.get_name() == 'None':
                all = False
                messages = []
            elif expr.has_form('List', None):
                all = False
                messages = []
                for item in expr.leaves:
                    if item.has_form('MessageName', 2):
                        symbol = item.leaves[0].get_name()
                        tag = item.leaves[1].get_string_value()
                        if symbol and tag:
                            messages.append((symbol, tag))
                        else:
                            raise ValueError
                    else:
                        raise ValueError
            else:
                raise ValueError
            return all, messages
        
        old_quiet_all, old_quiet_messages = evaluation.quiet_all, evaluation.quiet_messages.copy()
        try:
            quiet_expr = Expression('Quiet', expr, moff, mon)
            try:
                off_all, off_messages = get_msg_list(moff)
            except ValueError:
                evaluation.message('Quiet', 'anmlist', 2, quiet_expr)
                return
            try:
                on_all, on_messages = get_msg_list(mon)
            except ValueError:
                evaluation.message('Quiet', 'anmlist', 2, quiet_expr)
                return
            if off_all and on_all:
                evaluation.message('Quiet', 'allall', quiet_expr)
                return
            evaluation.quiet_all = off_all
            conflict = []
            for off in off_messages:
                if off in on_messages:
                    conflict.append(off)
                    break
            if conflict:
                evaluation.message('Quiet', 'conflict', quiet_expr, Expression('List', *(Expression('MessageName',
                    Symbol(symbol), String(tag)) for symbol, tag in conflict)))
                return
            for off in off_messages:
                evaluation.quiet_messages.add(off)
            for on in on_messages:
                evaluation.quiet_messages.discard(on)
            if on_all:
                evaluation.quiet_messages = set()
                
            return expr.evaluate(evaluation)
        finally:
            evaluation.quiet_all, evaluation.quiet_messages = old_quiet_all, old_quiet_messages

class MessageName(BinaryOperator):
    """
    'MessageName' is the head of message IDs of the form 'symbol::tag'.
    >> FullForm[a::b]
     = MessageName[a, "b"]
     
    The second parameter 'tag' is interpreted as a string.
    >> FullForm[a::"b"]
     = MessageName[a, "b"]
    """
    
    messages = {
        'messg': "Message cannot be set to `1`. It must be set to a string.",
    }
    
    operator = '::'
    precedence = 750
    attributes = ('HoldFirst',)
    
    default_formats = False
    
    formats = {
    }
    
    rules = {
        'MakeBoxes[MessageName[symbol_Symbol, tag_String], f:StandardForm|TraditionalForm|OutputForm]': 'RowBox[{MakeBoxes[symbol, f], "::", MakeBoxes[tag, f]}]',
        'MakeBoxes[MessageName[symbol_Symbol, tag_String], InputForm]': 'RowBox[{MakeBoxes[symbol, InputForm], "::", tag}]',
    }
    
    def apply(self, symbol, tag, evaluation):
        'MessageName[symbol_Symbol, tag_String]'
        
        pattern = Expression('MessageName', symbol, tag)
        return evaluation.definitions.get_value(symbol.get_name(), 'Messages', pattern, evaluation)
    
    def post_parse(self, expr):
        if len(expr.leaves) == 2 and expr.leaves[1].is_symbol():
            msg = expr.leaves[1].get_name()
            return Expression('MessageName', expr.leaves[0], String(msg))
        else:
            return expr
    
class General(Builtin):
    """
    'General' is a symbol to which all general-purpose messages are assigned.
    >> General::argr
     = `1` called with 1 argument; `2` arguments are expected.
    >> Message[Rule::argr, Rule, 2]
     : Rule called with 1 argument; 2 arguments are expected. 
    """
    
    messages = {
        'argb': "`1` called with `2` arguments; between `3` and `4` arguments are expected.",
        'argct': "`1` called with `2` arguments.",
        'argctu': "`1` called with 1 argument.",
        'argr': "`1` called with 1 argument; `2` arguments are expected.",
        'argrx': "`1` called with `2` arguments; `3` arguments are expected.",
        'argx': "`1` called with `2` arguments; 1 argument is expected.",
        'argt': "`1` called with `2` arguments; `3` or `4` arguments are expected.",
        'argtu': "`1` called with 1 argument; `2` or `3` arguments are expected.",
        'boxfmt': "`1` is not a box formatting type.",
        'color': "`1` is not a valid color or gray-level specification.",
        'divz': "The argument `1` should be nonzero.",
        'exact': "Argument `1` is not an exact number.",
        'fnsym': "First argument in `1` is not a symbol or a string naming a symbol.",
        'heads': "Heads `1` and `2` are expected to be the same.",
        'ilsnn': "Single or list of non-negative integers expected at position `1`.",
        'indet': "Indeterminate expression `1` encountered.",
        'innf': "Non-negative integer or Infinity expected at position `1`.",
        'int': "Integer expected.",
        'intp': "Positive integer expected.",
        'intnn': "Non-negative integer expected.",
        'iterb': "Iterator does not have appropriate bounds.",
        'ivar': "`1` is not a valid variable.",
        'level': "Level specification `1` is not of the form n, {n}, or {m, n}.",
        'locked': "Symbol `1` is locked.",
        'matsq': "Argument `1` is not a non-empty square matrix.",
        'nord': "Invalid comparison with `1` attempted.",
        'normal': "Nonatomic expression expected.",
        'noval': "Symbol `1` in part assignment does not have an immediate value.",
        'optb': "Optional object `1` in `2` is not a single blank.",
        'ovfl': "Overflow occured in computation.",
        'partd': "Part specification is longer than depth of object.",
        'partw': "Part `1` of `2` does not exist.",
        'plld': "Endpoints in `1` must be distinct machine-size real numbers.",
        'plln': "Limiting value `1` in `2` is not a machine-size real number.",
        'pspec': "Part specification `1` is neither an integer nor a list of integer.",
        'seqs': "Sequence specification expected, but got `1`.",
        'setp': "Part assignment to `1` could not be made",
        'setps': "`1` in the part assignment is not a symbol.",
        'span': "`1` is not a valid Span specification.",
        'string': "String expected.",
        'sym': "Argument `1` at position `2` is expected to be a symbol.",
        'tag': "Rule for `1` can only be attached to `2`.",
        'vrule': "Cannot set `1` to `2`, which is not a valid list of replacement rules.",
        'write': "Tag `1` in `2` is Protected.",
        'wrsym': "Symbol `1` is Protected.",
        
        # Self-defined messages
        #'rep': "`1` is not a valid replacement rule.",
        'options': "`1` is not a valid list of option rules.",
        'timeout': "Timeout reached.",
        'syntax': "`1`",
        'invalidargs': "Invalid arguments.",
        
        'notboxes': "`1` is not a valid box structure.",
    }
    
class Print(Builtin):
    """
    >> Print["Hello world!"]
     | Hello world!
    >> Print["The answer is ", 7 * 6, "."]
     | The answer is 42.
    """
    
    def apply(self, expr, evaluation):
        'Print[expr__]'
        
        expr = expr.get_sequence()
        expr = Expression('Row', Expression('List', *expr))
        evaluation.print_out(expr)
        return Symbol('Null')
    
class FullForm(Builtin):
    """
    >> FullForm[a + b * c]
     = Plus[a, Times[b, c]]
    >> FullForm[2/3]
     = Rational[2, 3]
    >> FullForm["A string"]
     = "A string"
    """
    
class StandardForm(Builtin):
    u"""
    >> StandardForm[a + b * c]
     = a + b c
    >> StandardForm["A string"]
     = A string
    'StandardForm' is used by default:
    >> "A string"
     = A string
    >> f'[x]
     = f'[x]
    """

class InputForm(Builtin):
    """
    >> InputForm[a + b * c]
     = a + b*c
    >> InputForm["A string"]
     = "A string"
    >> InputForm[f'[x]]
     = Derivative[1][f][x]
    >> InputForm[Derivative[1, 0][f][x]]
     = Derivative[1, 0][f][x]
    """
    
class OutputForm(Builtin):
    """
    >> OutputForm[f'[x]]
     = f'[x]
    >> OutputForm[Derivative[1, 0][f][x]]
     = Derivative[1, 0][f][x]
    >> OutputForm["A string"]
     = A string
    >> OutputForm[Graphics[Rectangle[]]]
     = -Graphics-
    """

class MathMLForm(Builtin):
    """
    >> MathMLForm[HoldForm[Sqrt[a^3]]]
     = <math><msqrt><msup><mi>a</mi> <mn>3</mn></msup></msqrt></math>
    """
    
    def apply_mathml(self, expr, evaluation):
        'MakeBoxes[expr_, MathMLForm]'
        
        boxes = MakeBoxes(expr).evaluate(evaluation)
        try:
            xml = boxes.boxes_to_xml(evaluation=evaluation)
        except BoxError:
            evaluation.message('General', 'notboxes', String('%s' % boxes))
            xml = ''
        #mathml = '<math><mstyle displaystyle="true">%s</mstyle></math>' % xml #convert_box(boxes)
        mathml = '<math>%s</math>' % xml #convert_box(boxes)
        return Expression('RowBox', Expression('List', String(mathml)))
    
class TeXForm(Builtin):
    r"""
    >> TeXForm[HoldForm[Sqrt[a^3]]]
     = \sqrt{a^3}
     
    #> {"hi","you"} //InputForm //TeXForm
     = \left\{\text{"hi"}, \text{"you"}\right\}
    """
    
    def apply_tex(self, expr, evaluation):
        'MakeBoxes[expr_, TeXForm]'
        
        boxes = MakeBoxes(expr).evaluate(evaluation)
        try:
            tex = boxes.boxes_to_tex(evaluation=evaluation)
            tex = MULTI_NEWLINE_RE.sub('\n', tex)   # replace multiple newlines by a single newline (relevent between asy-blocks)
        except BoxError:
            evaluation.message('General', 'notboxes', String('%s' % boxes))
            tex = ''
        return Expression('RowBox', Expression('List', String(tex)))
    
class Style(Builtin):
    options = {
        'ImageSizeMultipliers': 'Automatic',
    }
    
    rules = {
        'MakeBoxes[Style[expr_, OptionsPattern[Style]], f_]': 'StyleBox[MakeBoxes[expr, f], ImageSizeMultipliers->OptionValue[ImageSizeMultipliers]]',
    }
    
class Precedence(Builtin):
    """
    <dl>
    <dt>'Precedence[$op$]'
        <dd>returns the precedence of the built-in operator $op$.
    </dl>
    
    >> Precedence[Plus]
     = 310.
    >> Precedence[Plus] < Precedence[Times]
     = True
    
    Unknown symbols have precedence 670:
    >> Precedence[f]
     = 670.
    Other expressions have precedence 1000:
    >> Precedence[a + b]
     = 1000. 
    """
    
    def apply(self, expr, evaluation):
        'Precedence[expr_]'
        
        from mathics.builtin import builtins 
        
        name = expr.get_name()
        precedence = 1000
        if name:
            builtin = builtins.get(name)
            if builtin is not None and isinstance(builtin, Operator):
                precedence = builtin.precedence
            else:
                precedence = 670
        return Real(precedence)

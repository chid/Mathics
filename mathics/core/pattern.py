# -*- coding: utf8 -*-
# cython: profile=True

u"""
    Mathics: a general-purpose computer algebra system
    Copyright (C) 2011 Jan Pöschko

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from mathics.core.expression import Expression, Symbol, Integer, Rational, Real, Number
from mathics.core.util import subsets, subranges, permutations

from mathics.core.pattern_nocython import StopGenerator #, Pattern #, ExpressionPattern
from mathics.core import pattern_nocython


        
def Pattern_create(expr):
    from mathics.builtin import pattern_objects
    #from mathics.core.pattern import AtomPattern, ExpressionPattern
    
    name = expr.get_head_name()
    pattern_object = pattern_objects.get(name)
    if pattern_object is not None:
        return pattern_object(expr)
    if expr.is_atom():
        return AtomPattern(expr)
    else:
        return ExpressionPattern(expr)
    
class StopGenerator_Pattern(StopGenerator):
    pass
        
class Pattern(object):
    #@staticmethod
    #def create(expr):
    
    create = staticmethod(Pattern_create)
        
    def match(self, yield_func, expression, vars, evaluation, head=None, leaf_index=None, leaf_count=None,
        fully=True, wrap_oneid=True):
        raise NotImplementedError
    
    """def match(self, expression, vars, evaluation, head=None, leaf_index=None, leaf_count=None,
        fully=True, wrap_oneid=True):
        #raise NotImplementedError
        result = []
        def yield_func(vars, rest):
            result.append(vars, rest)
        self._match(yield_func, expression, vars, evaluation, head, leaf_index, leaf_count,
            fully, wrap_oneid)
        return result"""
    
    def does_match(self, expression, evaluation, vars=None, fully=True):
        
        if vars is None:
            vars = {}
        #for sub_vars, rest in self.match(expression, vars, evaluation, fully=fully):
        #    return True
        def yield_match(sub_vars, rest):
            raise StopGenerator_Pattern(True)
        try:
            self.match(yield_match, expression, vars, evaluation, fully=fully)
        except StopGenerator_Pattern, exc:
            return exc.value
        return False
        
    def get_name(self):
        return self.expr.get_name()
    def is_atom(self):
        return self.expr.is_atom()
    def get_head_name(self):
        return self.expr.get_head_name()
    def same(self, other):
        return self.expr.same(other.expr)
    def get_head(self):
        return self.expr.get_head()
    def get_leaves(self):
        return self.expr.get_leaves()
    def get_sort_key(self, pattern_sort=False):
        return self.expr.get_sort_key(pattern_sort=pattern_sort)
    def get_lookup_name(self):
        return self.expr.get_lookup_name()
    def get_attributes(self, definitions):
        return self.expr.get_attributes(definitions)
    def get_sequence(self):
        return self.expr.get_sequence()
    def get_option_values(self):
        return self.expr.get_option_values()
    def has_form(self, *args):
        return self.expr.has_form(*args)
    
    def get_match_candidates(self, leaves, expression, attributes, evaluation, vars={}):
        return []
    def get_match_candidates_count(self, leaves, expression, attributes, evaluation, vars={}):
        return len(self.get_match_candidates(leaves, expression, attributes, evaluation, vars))

class AtomPattern(Pattern):
    def __init__(self, expr):
        self.atom = expr
        self.expr = expr
                
    def __repr__(self):
        return '<AtomPattern: %s>' % self.atom
        
    def match(self, yield_func, expression, vars, evaluation, head=None, leaf_index=None, leaf_count=None,
        fully=True, wrap_oneid=True):
        
        if expression.same(self.atom):
            #yield vars, None
            yield_func(vars, None)
    
    def get_match_candidates(self, leaves, expression, attributes, evaluation, vars={}):
        return [leaf for leaf in leaves if leaf.same(self.atom)]
            
    def get_match_count(self, vars={}):
        return (1, 1)


#class StopGenerator_ExpressionPattern_match(StopGenerator):
#    pass

class ExpressionPattern(Pattern):
    #get_pre_choices = pattern_nocython.get_pre_choices
    match = pattern_nocython.match
    
    def get_pre_choices(self, yield_func, expression, attributes, vars):
        if 'Orderless' in attributes:
            self.sort()
            patterns = self.filter_leaves('Pattern')
            groups = {}
            prev_pattern = prev_name = None
            for pattern in patterns:
                name = pattern.leaves[0].get_name()
                existing = vars.get(name, None)
                if existing is None:
                    # There's no need for pre-choices if the variable is already set.
                    if name == prev_name:
                        if name in groups:
                            groups[name].append(pattern)
                        else:
                            groups[name] = [prev_pattern, pattern]
                    prev_pattern = pattern
                    prev_name = name
            expr_groups = {}
            prev_leaf = None
            for leaf in expression.leaves:
                if leaf in expr_groups:
                    expr_groups[leaf] += 1
                else:
                    expr_groups[leaf] = 1
            
            def per_name(yield_name, groups, vars):
                " Yields possible variable settings (dictionaries) for the remaining pattern groups "
                
                if groups:
                    name, patterns = groups[0]
                    
                    match_count = [0, None]
                    for pattern in patterns:
                        sub_match_count = pattern.get_match_count()
                        if sub_match_count[0] > match_count[0]:
                            match_count[0] = sub_match_count[0]
                        if match_count[1] is None or (sub_match_count[1] is not None and sub_match_count[1] < match_count[1]):
                            match_count[1] = sub_match_count[1]
                    possibilities = [{}]
                    sum = 0
                    
                    def per_expr(yield_expr, expr_groups, sum=0):
                        """ Yields possible values (sequence lists) for the current variable (name),
                        taking into account the (expression, count)'s in expr_groups
                        """
                        
                        if expr_groups:
                            expr, count = expr_groups[0]
                            max_per_pattern = count / len(patterns)
                            for per_pattern in range(max_per_pattern, -1, -1):
                                for next in per_expr(expr_groups[1:], sum + per_pattern):
                                    yield_expr([expr] * per_pattern + next)                            
                        else:
                            if sum >= match_count[0]:
                                yield_expr([])
                             
                    #for sequence in per_expr(expr_groups.items()):
                    def yield_expr(sequence):
                        wrappings = self.get_wrappings(sequence, match_count[1], expression, attributes)
                        for wrapping in wrappings:
                            #for next in per_name(groups[1:], vars):
                            def yield_next(next):
                                setting = next.copy()
                                setting[name] = wrapping
                                yield_name(setting)
                            per_name(yield_next, groups[1:], vars)
                    per_expr(yield_expr, expr_groups.items())
                else: # no groups left
                    yield_name(vars)
            
            #for setting in per_name(groups.items(), vars):
            def yield_name(setting):
                yield_func(setting)
            per_name(yield_name, groups.items(), vars)
        else:
            yield_func(vars) 
    
    
    def __init__(self, expr):
        self.head = Pattern.create(expr.head)
        self.leaves = [Pattern.create(leaf) for leaf in expr.leaves]
        self.expr = expr
        
    def filter_leaves(self, head_name):
        return [leaf for leaf in self.leaves if leaf.get_head_name() == head_name]
        
    def __repr__(self):
        return '<ExpressionPattern: %s>' % self.expr
    
    def get_match_count(self, vars={}):
        return (1, 1)
        
    def get_wrappings(self, yield_func, items, max_count, expression, attributes, include_flattened=True):
        if len(items) == 1:
            yield_func(items[0])
        else:
            if max_count is None or len(items) <= max_count:
                if 'Orderless' in attributes:
                    for perm in permutations(items):
                        sequence = Expression('Sequence', *perm)
                        sequence.pattern_sequence = True
                        yield_func(sequence)
                else:
                    sequence = Expression('Sequence', *items)
                    sequence.pattern_sequence = True
                    yield_func(sequence)
            if 'Flat' in attributes and include_flattened:
                yield_func(Expression(expression.get_head(), *items))
        
    def match_leaf(self, yield_func, leaf, rest_leaves, rest_expression, vars, expression, attributes,
        evaluation, leaf_index=1, leaf_count=None, first=False, fully=True, depth=1, wrap_oneid=True):
        
        if rest_expression is None:
            rest_expression = ([], [])
            
        evaluation.check_stopped()
            
        match_count = leaf.get_match_count(vars)
        leaf_candidates = leaf.get_match_candidates(rest_expression[1], #leaf.candidates,
            expression, attributes, evaluation, vars)
        
        if len(leaf_candidates) < match_count[0]:
            return
        
        # STRANGE: candidate in leaf_candidates causes BusError for Real ^ Integer (e.g. 2.0^3),
        # when not converted to a set!
        leaf_candidates = set(leaf_candidates)
        
        candidates = rest_expression[1]
        
        # "Artificially" only use more leaves than specified for some kind of pattern.
        # TODO: This could be further optimized!
        try_flattened = ('Flat' in attributes) and ( \
            leaf.get_head_name() in ('Pattern', 'PatternTest', 'Condition', 'Optional',
                'Blank', 'BlankSequence', 'BlankNullSequence', 'Alternatives', 'OptionsPattern',
                'Repeated', 'RepeatedNull'))
        
        if try_flattened:
            set_lengths = (match_count[0], None)
        else:
            set_lengths = match_count
            
        # try_flattened is used later to decide whether wrapping of leaves into one operand may occur.
        # This can of course also be when flat and same head.
        try_flattened = try_flattened or (('Flat' in attributes) and leaf.get_head() == expression.head)
            
        less_first = len(rest_leaves) > 0
            
        if 'Orderless' in attributes:
            sets = None
            if leaf.get_head_name() == 'Pattern':
                varname = leaf.leaves[0].get_name()
                existing = vars.get(varname, None)
                if existing is not None:
                    head = existing.get_head()
                    if head.get_name() == 'Sequence' or ('Flat' in attributes and head == expression.get_head()):
                        needed = existing.leaves
                    else:
                        needed = [existing]
                    available = candidates[:]
                    for needed_leaf in needed:
                        if needed_leaf in available and needed_leaf in leaf_candidates:
                            available.remove(needed_leaf)
                        else:
                            return
                    sets = [(needed, ([], available))]
                   
            if sets is None:
                sets = subsets(candidates, included=leaf_candidates, less_first=less_first, *set_lengths)
        else:
            sets = subranges(candidates, flexible_start=first and not fully, included=leaf_candidates, less_first=less_first, *set_lengths)
            
        for items, items_rest in sets:
            # Include wrappings like Plus[a, b] only if not all items taken
            # - in that case we would match the same expression over and over again.
            
            include_flattened = try_flattened and 0 < len(items) < len(expression.leaves)
        
            # Don't try flattened when the expression would remain the same!
            
            #wrappings = self.get_wrappings(items, match_count[1], expression, attributes,
            #    include_flattened=include_flattened)
            #for item in wrappings:
            def yield_wrapping(item):
                def match_yield(new_vars, _):
                    if rest_leaves:
                        def leaf_yield(next_vars, next_rest):
                            if next_rest is None:
                                next_rest = ([], [])
                            #yield next_vars, (rest_expression[0] + items_rest[0], next_rest[1])
                            yield_func(next_vars, (rest_expression[0] + items_rest[0], next_rest[1]))
                        
                        self.match_leaf(leaf_yield, rest_leaves[0], rest_leaves[1:], items_rest, new_vars,
                            expression, attributes, evaluation, fully=fully, depth=depth+1,
                            leaf_index=leaf_index+1, leaf_count=leaf_count, wrap_oneid=wrap_oneid)
                        #for next_vars, next_rest in recursion:
                    else:
                        if not fully or (not items_rest[0] and not items_rest[1]):
                            yield_func(new_vars, items_rest)
                            #yield new_vars, items_rest
                
                leaf.match(match_yield, item, vars, evaluation, fully=True,
                    head=expression.head, leaf_index=leaf_index, leaf_count=leaf_count, wrap_oneid=wrap_oneid)
                    
                # Need not fully match, as in g[a+b+c+d,a] against g[x_+y_,x_].
                #for new_vars, _ in leaf.match(item, vars, evaluation, fully=True,
                #    head=expression.head, leaf_index=leaf_index, leaf_count=leaf_count, wrap_oneid=wrap_oneid):
            
            self.get_wrappings(yield_wrapping, items, match_count[1], expression, attributes,
                include_flattened=include_flattened)
                    
        
    def get_match_candidates(self, leaves, expression, attributes, evaluation, vars={}):
        """
        Finds possible leaves that could match the pattern, ignoring future pattern variable definitions,
        but taking into account already fixed variables.
        """
        # TODO: fixed_vars!
        
        return [leaf for leaf in leaves if self.does_match(leaf, evaluation, vars)]
        
    def get_match_candidates_count(self, leaves, expression, attributes, evaluation, vars={}):
        """
        Finds possible leaves that could match the pattern, ignoring future pattern variable definitions,
        but taking into account already fixed variables.
        """
        # TODO: fixed_vars!
        
        count = 0
        for leaf in leaves:
            if self.does_match(leaf, evaluation, vars):
                count += 1
        return count
        
    def sort(self):        
        self.leaves.sort(key=lambda e: e.get_sort_key(pattern_sort=True))
        
    
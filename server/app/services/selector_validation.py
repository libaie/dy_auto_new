"""Validate geometry in selector JSON without normalizing legacy records."""
import math
import re

NORMALIZED_SPACES = {'screen_normalized', 'content_normalized', 'anchor_normalized'}
POSITION_SPACES = NORMALIZED_SPACES | {'screen_px', 'capture_px'}


def _number(value, path, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{path} must be a finite number')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{path} must be a finite number')
    if minimum is not None and value < minimum:
        raise ValueError(f'{path} must be >= {minimum}')
    if maximum is not None and value > maximum:
        raise ValueError(f'{path} must be <= {maximum}')


def _object(value, path):
    if not isinstance(value, dict):
        raise ValueError(f'{path} must be an object')
    return value


def _validate_strategy(strategy, purpose, path):
    strategy = _object(strategy, path)
    if purpose == 'page_detect' and (strategy.get('type') == 'coordinate' or 'position' in strategy):
        raise ValueError(f'{path}: page_detect cannot use coordinate evidence')

    anchor_needed = False
    if 'position' in strategy:
        position = _object(strategy['position'], f'{path}.position')
        space = position.get('space')
        if not isinstance(space, str) or space not in POSITION_SPACES:
            raise ValueError(f'{path}.position.space is invalid')
        for axis in ('x', 'y'):
            _number(position.get(axis), f'{path}.position.{axis}', 0,
                    1 if space in NORMALIZED_SPACES else None)
        anchor_needed = space == 'anchor_normalized'

    if 'offset' in strategy:
        offset = _object(strategy['offset'], f'{path}.offset')
        if offset.get('unit') not in ('px', 'dp', 'target_fraction'):
            raise ValueError(f'{path}.offset.unit is invalid')
        for axis in ('x', 'y'):
            _number(offset.get(axis), f'{path}.offset.{axis}')

    if 'region' in strategy:
        region = _object(strategy['region'], f'{path}.region')
        if not isinstance(region.get('space'), str) or region['space'] not in NORMALIZED_SPACES:
            raise ValueError(f'{path}.region.space is invalid')
        for edge in ('left', 'top', 'right', 'bottom'):
            _number(region.get(edge), f'{path}.region.{edge}', 0, 1)
        if region['left'] >= region['right'] or region['top'] >= region['bottom']:
            raise ValueError(f'{path}.region must have left < right and top < bottom')
        anchor_needed = anchor_needed or region['space'] == 'anchor_normalized'

    if 'anchor' in strategy:
        anchor = _object(strategy['anchor'], f'{path}.anchor')
        if anchor.get('type') not in ('text', 'id', 'desc', 'className'):
            raise ValueError(f'{path}.anchor.type must be text/id/desc/className')
        if not isinstance(anchor.get('value'), str) or not anchor['value'].strip():
            raise ValueError(f'{path}.anchor.value is required')
        if anchor.get('match_mode', 'exact') not in ('exact', 'contains'):
            raise ValueError(f'{path}.anchor.match_mode is invalid')
        if set(anchor) - {'type', 'value', 'match_mode'}:
            raise ValueError(f'{path}.anchor must be a single semantic selector')
    elif anchor_needed:
        raise ValueError(f'{path}.anchor is required for anchor_normalized')

    if 'source_resolution' in strategy:
        value = strategy['source_resolution']
        if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]*x[1-9][0-9]*', value):
            raise ValueError(f'{path}.source_resolution must be positive WIDTHxHEIGHT')
    if 'source_density' in strategy:
        _number(strategy['source_density'], f'{path}.source_density', 0)
        if strategy['source_density'] == 0:
            raise ValueError(f'{path}.source_density must be positive')
    if 'scales' in strategy:
        scales = strategy['scales']
        if not isinstance(scales, list) or not 1 <= len(scales) <= 5:
            raise ValueError(f'{path}.scales must contain one to five numbers')
        for index, scale in enumerate(scales):
            _number(scale, f'{path}.scales[{index}]', 0.25, 4)
    if 'threshold' in strategy:
        _number(strategy['threshold'], f'{path}.threshold', 0, 1)

    # Names are deliberately interpreted by strategy type, as in the device runtime.
    for axis in ('x_percent', 'y_percent'):
        if axis in strategy and strategy[axis] is not None:
            _number(strategy[axis], f'{path}.{axis}',
                    0 if strategy.get('type') == 'coordinate' else None,
                    1 if strategy.get('type') == 'coordinate' else None)
    for field in ('conditions', 'steps'):
        if field in strategy:
            children = strategy[field]
            if not isinstance(children, list):
                raise ValueError(f'{path}.{field} must be an array')
            for index, child in enumerate(children):
                _validate_strategy(child, purpose, f'{path}.{field}[{index}]')


def validate_selector_strategies(strategies, purpose='locate'):
    """Validate only supported geometry fields, retaining all other strategy data."""
    if not isinstance(strategies, list):
        raise ValueError('strategies must be an array')
    for index, strategy in enumerate(strategies):
        _validate_strategy(strategy, purpose, f'strategies[{index}]')

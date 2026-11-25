"""Endpoint-selected walks on a pinned network, without health optimization."""
import heapq
import math


def selected_walk(network, origin, goal, speed_m_s, max_duration_s, checkpoint=lambda: None):
    """Shortest horizontal mapped distance, preserving every source vertex.

    No topology repair, field-dependent detour, signal program or traffic replay.
    Crossing times are illustrative walking times, not clearance predictions.
    """
    if origin not in network['nodes'] or goal not in network['nodes']:
        raise ValueError('Select START and END on the pinned walking network')
    if origin == goal:
        raise ValueError('START and END must be different')
    if not math.isfinite(speed_m_s) or speed_m_s <= 0:
        raise ValueError('Walking speed must be positive and finite')
    if not math.isfinite(max_duration_s) or max_duration_s <= 0:
        raise ValueError('No current-city time coverage remains')
    component = {n: i for i, nodes in enumerate(network['components']) for n in nodes}
    if component.get(origin) != component.get(goal):
        raise ValueError('These endpoints have no mapped walking connection; choose a connected path')
    adjacent = {n: [] for n in network['nodes']}
    for index, edge in enumerate(network['edges']):
        length = sum(math.dist(a[:2], b[:2]) for a, b in zip(edge['points'], edge['points'][1:]))
        if not math.isfinite(length) or length <= 0:
            raise ValueError('Invalid pinned walking edge length')
        adjacent[edge['u']].append((edge['v'], length, index, False))
        adjacent[edge['v']].append((edge['u'], length, index, True))
    distances, previous, queue = {origin: 0.}, {}, [(0., origin)]
    limit = speed_m_s * max_duration_s
    while queue:
        checkpoint()
        distance, u = heapq.heappop(queue)
        if distance != distances[u]:
            continue
        if u == goal:
            break
        for v, length, index, reverse in adjacent[u]:
            candidate = distance + length
            if candidate <= limit + 1e-7 and candidate < distances.get(v, math.inf):
                distances[v] = candidate
                previous[v] = (u, index, reverse, length)
                heapq.heappush(queue, (candidate, v))
    if goal not in previous:
        raise ValueError(f'This walk exceeds the available {max_duration_s / 60:g} minutes of declared Health coverage; choose closer endpoints')
    path, v = [], goal
    while v != origin:
        u, index, reverse, length = previous[v]
        path.append((u, v, index, reverse, length))
        v = u
    timeline, keys, crossings, elapsed = [], [], [], 0.
    for u, v, index, reverse, length in reversed(path):
        edge = network['edges'][index]
        points = edge['points'][::-1] if reverse else edge['points']
        stop = elapsed + length / speed_m_s
        timeline.append(dict(kind='Walking', start=elapsed, end=stop, points=points))
        keys.append([u, v])
        if edge.get('crossing_id'):
            crossings.append(edge['crossing_id'])
        elapsed = stop
    return dict(edge_keys=keys, timeline=timeline, duration_s=elapsed,
                distance_m=distances[goal], crossing_ids=crossings)

"""Verification tests for the bounded route cache and LRU eviction."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.knowledge.store import KnowledgeStore
from app.models.stadium import StadiumModel
from app.models.state import StadiumSnapshot
from app.simulator.engine import StadiumSimulator
from app.simulator import fixtures
from app.tools.handlers import ToolContext, _shortest_path, _ROUTE_CACHE


@pytest.fixture()
def setup_ctx():
    # Setup mock/real dependencies
    sim = StadiumSimulator()
    model = fixtures.load_stadium_model()
    knowledge = KnowledgeStore()
    ctx = ToolContext(simulator=sim, model=model, knowledge=knowledge)
    return ctx


def test_route_cache_lru_eviction(setup_ctx):
    ctx = setup_ctx
    # Clear the route cache to start fresh
    _ROUTE_CACHE.clear()

    # 1. Fill the cache up to its limit (2048 entries)
    # We will use unique sources and destinations to generate unique cache keys
    # Let's populate 2048 items. Since the real wayfinding calculation is fast,
    # but running it 2048 times might take a couple of seconds, we can run it.
    # To speed up and avoid running the full Dijkstra graph search 2048 times,
    # we can also mock ctx.model to have no edges, so _shortest_path will fail
    # instantly and cache the result.
    # But let's just make sure it's fast by using a simplified ctx.model or bypassing _build_graph.
    # Wait, let's look at what _shortest_path does:
    # it uses id(ctx.model), snap.gates status, snap.crowd, and snap.incidents.
    # If we pass nonexistent waypoint IDs, Dijkstra fails immediately because the src waypoint is not in the graph or has no outgoing edges.
    # So we can query (ctx, f"SRC-{i}", f"DST-{i}", False) which will fail instantly and cache (None, 0.0).
    
    limit = 2048
    for i in range(limit):
        src = f"SRC-{i}"
        dst = f"DST-{i}"
        _shortest_path(ctx, src, dst, False)

    assert len(_ROUTE_CACHE) == limit

    # 2. Check the oldest and newest items in the OrderedDict.
    # Since OrderedDict preserves insertion order, the first item added (index 0) should be the first key.
    keys_list = list(_ROUTE_CACHE.keys())
    oldest_key = keys_list[0]
    assert oldest_key[1] == "SRC-0"  # src is the second element of cache_key tuple

    # 3. Add one more item (2049th)
    # This should trigger eviction of the oldest item ("SRC-0")
    _shortest_path(ctx, "SRC-2048", "DST-2048", False)
    assert len(_ROUTE_CACHE) == limit
    assert oldest_key not in _ROUTE_CACHE

    # The new oldest key should be "SRC-1"
    new_keys_list = list(_ROUTE_CACHE.keys())
    assert new_keys_list[0][1] == "SRC-1"


def test_route_cache_lru_hits_update_mru(setup_ctx):
    ctx = setup_ctx
    _ROUTE_CACHE.clear()

    # Fill the cache with 5 items (for illustration, we'll hit them to verify MRU updates,
    # but we need to verify it with the real 2048 limit)
    # Let's fill 2048 items.
    limit = 2048
    for i in range(limit):
        _shortest_path(ctx, f"SRC-{i}", f"DST-{i}", False)

    # Let's hit the oldest item ("SRC-0") to move it to the end (MRU)
    _shortest_path(ctx, "SRC-0", "DST-0", False)

    # Now "SRC-0" should be the last item in OrderedDict (most recently used),
    # and the new oldest item should be "SRC-1".
    keys_list = list(_ROUTE_CACHE.keys())
    assert keys_list[-1][1] == "SRC-0"
    assert keys_list[0][1] == "SRC-1"

    # Add the 2049th item. This should evict the oldest item, which is now "SRC-1".
    _shortest_path(ctx, "SRC-2048", "DST-2048", False)

    # Verify that "SRC-1" is evicted, but "SRC-0" is still in the cache.
    assert len(_ROUTE_CACHE) == limit
    
    # We find if the keys corresponding to SRC-1 and SRC-0 are present
    has_src_0 = any(k[1] == "SRC-0" for k in _ROUTE_CACHE.keys())
    has_src_1 = any(k[1] == "SRC-1" for k in _ROUTE_CACHE.keys())
    assert has_src_0 is True
    assert has_src_1 is False

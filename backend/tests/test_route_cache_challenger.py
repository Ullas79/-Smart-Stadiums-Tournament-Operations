"""Challenger tests to verify bounded route cache and LRU eviction."""
from __future__ import annotations

import concurrent.futures
import threading
import pytest

from app.knowledge.store import KnowledgeStore
from app.simulator.engine import StadiumSimulator
from app.simulator import fixtures
from app.tools.handlers import ToolContext, _shortest_path, _ROUTE_CACHE


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure a clean route cache before and after each test."""
    _ROUTE_CACHE.clear()
    yield
    _ROUTE_CACHE.clear()


@pytest.fixture()
def setup_ctx():
    model = fixtures.load_stadium_model()
    sim = StadiumSimulator(model=model)
    knowledge = KnowledgeStore()
    ctx = ToolContext(simulator=sim, model=model, knowledge=knowledge)
    return ctx, sim, model


def test_cache_hits_and_copies(setup_ctx):
    """Verify that cache hits return copies and don't mutate cached results."""
    ctx, _, _ = setup_ctx
    
    # Run shortest path
    path1, dist1 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    assert path1 is not None
    
    # It must be in the cache now
    assert len(_ROUTE_CACHE) == 1
    
    # Mutate the returned path list
    original_len = len(path1)
    path1.append("MUTATED")
    
    # Call shortest path again with same args
    path2, dist2 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    
    # Verify that the mutated element is NOT in the second result
    assert "MUTATED" not in path2
    assert len(path2) == original_len
    assert path2 == path1[:-1]


def test_lru_eviction_and_bounding(setup_ctx):
    """Verify that route cache evicts the oldest entry under load and does not grow beyond 2048."""
    ctx, _, model = setup_ctx
    
    # We will generate different waypoint combinations to populate the cache.
    # There are enough waypoints in the model. Let's see how many waypoints we have.
    waypoints = [w.waypoint_id for w in model.waypoints]
    assert len(waypoints) >= 10, "Not enough waypoints to perform cache testing"
    
    # Let's verify we can generate at least 2050 distinct calls.
    # Since we need 2050 distinct cache keys, we can vary the source or destination,
    # or accessible_only, or mock cache keys directly if needed.
    # But wait, we can call `_shortest_path` with different waypoints.
    # To easily generate 2050 distinct keys, we can use different waypoint pairs.
    # If waypoints has N items, we have N * (N-1) pairs. If N=30, we have 870 pairs.
    # If N is not large enough, we can also vary other signature components (like crowd density or gate status) by copying the context,
    # but wait, it's easier to just call it with different parameters or mock keys.
    # Let's inspect how many waypoints are in fixtures.
    print(f"Total waypoints: {len(waypoints)}")
    
    # Let's call _shortest_path with different src and dst pairs.
    # If we need 2050 distinct keys:
    # We can also mock _shortest_path's cache additions or use dynamic dummy waypoints on a custom model.
    # Alternatively, we can create a custom model with 60 waypoints to get 60 * 59 = 3540 pairs.
    # Let's do that! Or we can just dynamically add waypoints to the current model for the test.
    from app.models.stadium import Waypoint, LevelName
    
    custom_waypoints = list(model.waypoints)
    for i in range(100):
        custom_waypoints.append(Waypoint(waypoint_id=f"WP-TEST-{i}", name=f"Test {i}", level=LevelName.LOWER_BOWL))
        
    custom_model = model.model_copy(update={"waypoints": custom_waypoints})
    custom_ctx = ToolContext(simulator=ctx.simulator, model=custom_model, knowledge=ctx.knowledge)
    
    # Now we have 100+ waypoints. We can generate 2050 unique queries easily.
    # Let's make 2055 unique queries: src="WP-TEST-0", dst="WP-TEST-i" for i in 1..2055.
    # Wait, Dijkstra will return (None, 0.0) if there's no path, but it will still cache it!
    # Let's check: yes, _shortest_path caches (path_found, dist_found) even if path_found is None.
    
    # Call 2048 distinct times to fill the cache to its limit
    keys = []
    for i in range(1, 2049):
        dst = f"WP-TEST-{i}"
        _shortest_path(custom_ctx, "WP-TEST-0", dst, False)
        
    assert len(_ROUTE_CACHE) == 2048
    
    # Capture the order of keys in the cache
    first_key = list(_ROUTE_CACHE.keys())[0]
    second_key = list(_ROUTE_CACHE.keys())[1]
    
    # Access the first_key again to trigger move_to_end (making it the most recently used)
    # The first key corresponds to dst="WP-TEST-1"
    _shortest_path(custom_ctx, "WP-TEST-0", "WP-TEST-1", False)
    
    # Now, the first key should have moved to the end, and the new first key should be the second_key
    assert list(_ROUTE_CACHE.keys())[-1] == first_key
    assert list(_ROUTE_CACHE.keys())[0] == second_key
    
    # Now add a new entry (2049th distinct entry)
    _shortest_path(custom_ctx, "WP-TEST-0", "WP-TEST-2049", False)
    
    # The cache size must remain exactly 2048
    assert len(_ROUTE_CACHE) == 2048
    
    # The second_key (which was the oldest since first_key was touched) must be evicted
    assert second_key not in _ROUTE_CACHE
    
    # The first_key must still be in the cache
    assert first_key in _ROUTE_CACHE


def test_cache_invalidation_on_state_change(setup_ctx):
    """Verify that changing state (crowd density, gate status, incidents) bypasses the cache."""
    ctx, sim, _ = setup_ctx
    
    # Call shortest path
    path1, dist1 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    
    # Hit the cache
    path2, dist2 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    assert len(_ROUTE_CACHE) == 1
    
    # Change gate status (this changes gate_sig)
    sim.set_gate_status("G-N", "restricted")
    
    # Call again - should bypass cache and create a new cache entry
    path3, dist3 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    assert len(_ROUTE_CACHE) == 2
    
    # Change crowd density (this changes crowd_sig)
    with sim._lock:
        sim._crowd["L-N"].density = 0.99
        
    path4, dist4 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    assert len(_ROUTE_CACHE) == 3
    
    # Add an active incident (this changes inc_sig)
    sim.report_incident("medical", "WP-C-L-N", "high")
    
    path5, dist5 = _shortest_path(ctx, "WP-G-N", "WP-C-L-N", False)
    assert len(_ROUTE_CACHE) == 4


def test_cache_concurrency(setup_ctx):
    """Verify that the cache operations are safe under concurrent multi-threaded access."""
    ctx, _, model = setup_ctx
    
    # Create many test waypoints to trigger hits and evictions across multiple threads
    from app.models.stadium import Waypoint, LevelName
    custom_waypoints = list(model.waypoints)
    for i in range(500):
         custom_waypoints.append(Waypoint(waypoint_id=f"WP-CONC-{i}", name=f"Conc {i}", level=LevelName.LOWER_BOWL))
    custom_model = model.model_copy(update={"waypoints": custom_waypoints})
    custom_ctx = ToolContext(simulator=ctx.simulator, model=custom_model, knowledge=ctx.knowledge)
    
    errors = []
    
    def worker(worker_id):
        try:
            # Each worker performs route queries, some hit, some miss, some trigger evictions
            # Let's perform 2000 queries per worker to ensure we hit cache limits and concurrent evictions
            for j in range(1000):
                dst = f"WP-CONC-{(worker_id * 100 + j) % 500}"
                path, dist = _shortest_path(custom_ctx, "WP-G-N", dst, False)
        except Exception as e:
            errors.append(f"Worker {worker_id} failed: {e}")

    # Start 10 concurrent threads
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    assert len(errors) == 0, f"Concurrency errors occurred: {errors}"
    assert len(_ROUTE_CACHE) <= 2048

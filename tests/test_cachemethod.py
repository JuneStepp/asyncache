import operator
import unittest

from cachetools import LRUCache, keys

from asyncache import cachedmethod


class AsyncCached:
    def __init__(self, cache, count=0):
        self.cache = cache
        self.count = count

    @cachedmethod(operator.attrgetter("cache"))
    async def get(self, value):
        count = self.count
        self.count += 1
        return count

    @cachedmethod(operator.attrgetter("cache"), key=keys.typedkey)
    async def get_typed(self, value):
        count = self.count
        self.count += 1
        return count


class AsyncLocked:
    def __init__(self, cache):
        self.cache = cache
        self.count = 0

    @cachedmethod(operator.attrgetter("cache"), lock=lambda self: self)
    async def get(self, value):
        return self.count

    async def __aenter__(self):
        self.count += 1

    async def __aexit__(self, *exc):
        pass


class CachedMethodTestAsync(unittest.IsolatedAsyncioTestCase):
    async def test_dict(self):
        cached = AsyncCached({})

        self.assertEqual((await cached.get(0)), 0)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1.0)), 1)
        self.assertEqual((await cached.get(1.0)), 1)

        cached.cache.clear()
        self.assertEqual((await cached.get(1)), 2)

    async def test_typed_dict(self):
        cached = AsyncCached(LRUCache(maxsize=2))

        self.assertEqual((await cached.get_typed(0)), 0)
        self.assertEqual((await cached.get_typed(1)), 1)
        self.assertEqual((await cached.get_typed(1)), 1)
        self.assertEqual((await cached.get_typed(1.0)), 2)
        self.assertEqual((await cached.get_typed(1.0)), 2)
        self.assertEqual((await cached.get_typed(0.0)), 3)
        self.assertEqual((await cached.get_typed(0)), 4)

    async def test_lru(self):
        cached = AsyncCached(LRUCache(maxsize=2))

        self.assertEqual((await cached.get(0)), 0)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1.0)), 1)
        self.assertEqual((await cached.get(1.0)), 1)

        cached.cache.clear()
        self.assertEqual((await cached.get(1)), 2)

    async def test_typed_lru(self):
        cached = AsyncCached(LRUCache(maxsize=2))

        self.assertEqual((await cached.get_typed(0)), 0)
        self.assertEqual((await cached.get_typed(1)), 1)
        self.assertEqual((await cached.get_typed(1)), 1)
        self.assertEqual((await cached.get_typed(1.0)), 2)
        self.assertEqual((await cached.get_typed(1.0)), 2)
        self.assertEqual((await cached.get_typed(0.0)), 3)
        self.assertEqual((await cached.get_typed(0)), 4)

    async def test_nospace(self):
        cached = AsyncCached(LRUCache(maxsize=0))

        self.assertEqual((await cached.get(0)), 0)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1)), 2)
        self.assertEqual((await cached.get(1.0)), 3)
        self.assertEqual((await cached.get(1.0)), 4)

    async def test_nocache(self):
        cached = AsyncCached(None)

        self.assertEqual((await cached.get(0)), 0)
        self.assertEqual((await cached.get(1)), 1)
        self.assertEqual((await cached.get(1)), 2)
        self.assertEqual((await cached.get(1.0)), 3)
        self.assertEqual((await cached.get(1.0)), 4)

    async def test_weakref(self):
        import fractions
        import gc
        import weakref

        # in Python 3.7, `int` does not support weak references even
        # when subclassed, but Fraction apparently does...
        class Int(fractions.Fraction):
            def __add__(self, other):
                return Int(fractions.Fraction.__add__(self, other))

        cached = AsyncCached(weakref.WeakValueDictionary(), count=Int(0))

        self.assertEqual((await cached.get(0)), 0)
        gc.collect()
        self.assertEqual((await cached.get(0)), 1)

        ref = await cached.get(1)
        self.assertEqual(ref, 2)
        self.assertEqual((await cached.get(1)), 2)
        self.assertEqual((await cached.get(1.0)), 2)

        ref = await cached.get_typed(1)
        self.assertEqual(ref, 3)
        self.assertEqual((await cached.get_typed(1)), 3)
        self.assertEqual((await cached.get_typed(1.0)), 4)

        cached.cache.clear()
        self.assertEqual((await cached.get(1)), 5)

    async def test_locked_dict(self):
        cached = AsyncLocked({})

        self.assertEqual((await cached.get(0)), 1)
        self.assertEqual((await cached.get(1)), 3)
        self.assertEqual((await cached.get(1)), 3)
        self.assertEqual((await cached.get(1.0)), 3)
        self.assertEqual((await cached.get(2.0)), 7)

    async def test_locked_nocache(self):
        cached = AsyncLocked(None)

        self.assertEqual((await cached.get(0)), 0)
        self.assertEqual((await cached.get(1)), 0)
        self.assertEqual((await cached.get(1)), 0)
        self.assertEqual((await cached.get(1.0)), 0)
        self.assertEqual((await cached.get(1.0)), 0)

    async def test_locked_nospace(self):
        cached = AsyncLocked(LRUCache(maxsize=0))

        self.assertEqual((await cached.get(0)), 1)
        self.assertEqual((await cached.get(1)), 3)
        self.assertEqual((await cached.get(1)), 5)
        self.assertEqual((await cached.get(1.0)), 7)
        self.assertEqual((await cached.get(1.0)), 9)

    async def test_wrapped(self):
        cache = {}
        cached = AsyncCached(cache)

        self.assertEqual(len(cache), 0)
        self.assertEqual(await cached.get.__wrapped__(cached, 0), 0)
        self.assertEqual(len(cache), 0)
        self.assertEqual(await cached.get(0), 1)
        self.assertEqual(len(cache), 1)
        self.assertEqual(await cached.get(0), 1)
        self.assertEqual(len(cache), 1)

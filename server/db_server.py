import aiopg
import aiozmq.rpc
import asyncio
import os
import psycopg2
from psycopg2.extras import Json
from zmqrpc.translation_table import translation_table

from engine import models
from engine.models.base import ModelsDict

if os.environ['DB_PASS']:
    dsn = '''dbname={DB_NAME} user={DB_USER} password={DB_PASS}
 host={DB_PORT_5432_TCP_ADDR} port={DB_PORT_5432_TCP_PORT}'''
else:
    dsn = '''dbname={DB_NAME} user={DB_USER}
 host={DB_PORT_5432_TCP_ADDR} port={DB_PORT_5432_TCP_PORT}'''

dsn = dsn.format(**os.environ)


class DBServerHandler(aiozmq.rpc.AttrHandler):

    def __init__(self, pool):
        super().__init__()
        self._pool = pool

    @asyncio.coroutine
    def _load_world(self, world_id, cursor):
        query = '''
        SELECT id, name, params, created FROM world_world WHERE id=%s
        '''
        yield from cursor.execute(query, (world_id,))
        data = yield from cursor.fetchone()
        world = models.World(data)
        buildings = yield from self.get_buildings()
        world.buildings = buildings
        units = yield from self.get_units()
        world.units = units
        return world

    @asyncio.coroutine
    def _load_regions(self, world, cursor):
        query = '''
        SELECT *, ST_AsGeoJSON(geom) as geom FROM world_region WHERE world_id=%s
        '''
        yield from cursor.execute(query, (world.id,))
        data = yield from cursor.fetchall()

        query = '''
        SELECT rn.from_region_id AS region_id, array_agg(rn.to_region_id) AS neighbors
        FROM world_region_neighbors rn JOIN world_region r ON (rn.from_region_id=r.id)
        WHERE r.world_id=%s GROUP BY from_region_id
        '''
        yield from cursor.execute(query, (world.id,))
        neighbors_data = yield from cursor.fetchall()

        regions = {}
        for row in data:
            region = models.Region(row, world=world)
            regions[region.id] = region

        for row in neighbors_data:
            for neighbor_id in row['neighbors']:
                regions[row['region_id']].neighbors[neighbor_id] = regions[neighbor_id]

        world.regions = regions

    @asyncio.coroutine
    def _load_cities(self, world, cursor):
        query = '''
        SELECT *, ST_AsGeoJSON(coords) as coords FROM world_city WHERE world_id=%s
        '''
        yield from cursor.execute(query, (world.id,))
        data = yield from cursor.fetchall()

        for row in data:
            # Load active quest
            row['active_quests'] = {}

            # Load buildings
            row['buildings'] = row['buildings'] or {}

            # fix buildings keys
            row['buildings'] = {int(key): value for (key, value) in row['buildings'].items()}

            # Fill building that does not exist. This may happen if new building was added
            for building_id in world.buildings.keys():
                if building_id not in row['buildings']:
                    row['buildings'][building_id] = {
                        'level': 0,
                        'in_progress': False,
                        'building_id': building_id,
                        'build_progress': 0
                    }

            # Load units
            row['units'] = row['units'] or {}

            # fix units keys
            row['units'] = {int(key): value for (key, value) in row['units'].items()}

            # Fill units that does not exist. This may happen if new unit was added
            for unit_id in world.units.keys():
                if unit_id not in row['units']:
                    row['units'][unit_id] = {
                        'number': 0,
                        'queue': 0,
                        'unit_id': unit_id
                    }

            region = world.regions[row['region_id']]
            city = models.City(row, world=world, region=region)
            region.cities[city.id] = city
            world.cities[city.id] = city

    def _load_quests(self, world, cursor):
        query = '''
        SELECT
            q.*,
            ARRAY(
                SELECT qc.city_id FROM events_quest_cities qc WHERE qc.quest_id=q.id
            ) AS cities,
            ARRAY(
                SELECT qr.region_id FROM events_quest_regions qr WHERE qr.quest_id=q.id
            ) AS regions
        FROM events_quest q
        WHERE q.finished IS NULL AND q.world_id=%s
        '''
        # FIXME: Should we load all participations for event's quests?
        participation_query = '''
        SELECT * FROM events_participation WHERE quest_id=%s AND finished IS NULL
        '''

        yield from cursor.execute(query, (world.id,))
        data = yield from cursor.fetchall()

        for row in data:
            quest = models.Quest(row)
            world.quests[quest.id] = quest
            # yield from cursor.execute(participation_query, (quest.id,))
            # participation_data = yield from cursor.fetchall()

    @aiozmq.rpc.method
    @asyncio.coroutine
    def get_world(self, world_id: int):
        with (yield from self._pool.cursor()) as cursor:
            world = yield from self._load_world(world_id, cursor)
            yield from self._load_regions(world, cursor)
            yield from self._load_cities(world, cursor)
            yield from self._load_quests(world, cursor)
            return world

    @aiozmq.rpc.method
    @asyncio.coroutine
    def get_active_worlds(self):
        with (yield from self._pool.cursor()) as cursor:
            yield from cursor.execute('SELECT id FROM world_world')
            worlds = yield from cursor.fetchall()
            return worlds

    @aiozmq.rpc.method
    @asyncio.coroutine
    def get_buildings(self):
        with (yield from self._pool.cursor()) as cursor:
            yield from cursor.execute('SELECT * FROM building_buildingtier ORDER BY level')
            data = yield from cursor.fetchall()
            building_tiers = {}
            for row in data:
                building_tiers.setdefault(row['building_id'], {})[row['level']] = row

            yield from cursor.execute('SELECT * FROM building_building')
            data = yield from cursor.fetchall()
            buildings = ModelsDict()
            for row in data:
                row['tiers'] = building_tiers[row['id']]
                buildings[row['id']] = models.Building(row)

            return buildings

    @aiozmq.rpc.method
    @asyncio.coroutine
    def get_units(self):
        with (yield from self._pool.cursor()) as cursor:
            yield from cursor.execute('SELECT * FROM units_type')
            data = yield from cursor.fetchall()
            unit_types = {}
            for row in data:
                unit_types[row['id']] = row

            yield from cursor.execute('SELECT * FROM units_unit')
            data = yield from cursor.fetchall()

            units = ModelsDict()
            for row in data:
                row['upgradeable_to'] = []
                row['type'] = unit_types[row['type_id']]
                units[row['id']] = models.Unit(row)

            for unit in units.values():
                if unit.parent_id:
                    units[unit.parent_id].upgradeable_to.append(unit.id)

            return units

    @aiozmq.rpc.method
    @asyncio.coroutine
    def get_user_data(self, user_id: int):
        with (yield from self._pool.cursor()) as cursor:
            yield from cursor.execute('SELECT id FROM world_city WHERE user_id=%s', (user_id,))
            data = yield from cursor.fetchone()
            return {
                'city_id': data['id']
            }

    @aiozmq.rpc.method
    @asyncio.coroutine
    def save_world(self, world):
        with (yield from self._pool.cursor()) as cursor:
            for city in world.cities.values():
                data = city.to_dict(with_initial=True)
                yield from cursor.execute(
                    'UPDATE world_city SET buildings=%s, stats=%s WHERE id=%s',
                    (Json(data['buildings']), Json(data['stats']), city.id))


def main():
    loop = asyncio.get_event_loop()
    pool = loop.run_until_complete(
        aiopg.create_pool(dsn, cursor_factory=psycopg2.extras.RealDictCursor))
    handler = DBServerHandler(pool)
    server = aiozmq.rpc.serve_rpc(
        handler,
        bind='tcp://0.0.0.0:5000',
        translation_table=translation_table,
        loop=loop,
        log_exceptions=True)
    loop.run_until_complete(server)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        loop.close()

    print("DONE")

if __name__ == '__main__':
    main()

'use strict';
import { Flux } from 'flummox';

import BuildingsActions from './actions/BuildingsActions';
import CityActions from './actions/CityActions';
import QuestsActions from './actions/QuestsActions';
import UnitsActions from './actions/UnitsActions';
import WorldActions from './actions/WorldActions';

import BuildingsStore from './stores/BuildingsStore';
import CityStore from './stores/CityStore';
import QuestsStore from './stores/QuestsStore';
import UnitsStore from './stores/UnitsStore';
import WorldStore from './stores/WorldStore';


export default class Application extends Flux {

    constructor(rpc) {
        super();
        this.rpc = rpc;

        const worldActions = this.createActions('worldActions', WorldActions, { rpc });
        this.createStore('worldStore', WorldStore, { actions: worldActions });

        const buildingsActions = this.createActions('buildingsActions', BuildingsActions, { rpc });
        this.createStore('buildingsStore', BuildingsStore, { actions: buildingsActions });

        const unitsActions = this.createActions('unitsActions', UnitsActions, { rpc });
        this.createStore('unitsStore', UnitsStore, { actions: unitsActions });

        const cityActions = this.createActions('cityActions', CityActions, { rpc });
        this.createStore('cityStore', CityStore, { actions: cityActions });

        const questsActions = this.createActions('questsActions', QuestsActions, { rpc });
        this.createStore('questsStore', QuestsStore, { actions: questsActions });

        rpc.subscribe('update:world', (world, topic) => {
            this.getActions('worldActions').updateWorld(world);
        });

        rpc.subscribe('update:quests', (quests, topic) => {
            this.getActions('questsActions').updateQuests(quests);
        });

        rpc.subscribe('update:city', (city, topic) => {
            this.getActions('cityActions').updateCity(city);
        });
    }
}

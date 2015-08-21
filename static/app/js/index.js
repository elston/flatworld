import FluxComponent from 'flummox/component';
import React from 'react';

import AppFlux from './AppFlux'
import router from './router';
import Rpc from './Rpc'

window.React = React; // For React Developer Tools


async function main() {
    const url = 'ws://127.0.0.1:9000'
    console.log('Connectiong...', url);
    const rpc = new Rpc(url);
    await rpc.connect();
    console.log('Connected');

    const flux = new AppFlux(rpc);

    router.run(function (Handler, state) {
        React.render(
            <FluxComponent flux={flux}>
                <Handler {...state.params} />
            </FluxComponent>,
            document.getElementById('app')
        );
    });
}

main();
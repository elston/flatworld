export function notify(message, type) {
    $.growl({
        message: message
    },{
        type: type,
        allow_dismiss: false,
        label: 'Cancel',
        className: 'btn-xs btn-inverse',
        placement: {
            from: 'top',
            align: 'right'
        },
        delay: 2500,
        offset: {
            x: 20,
            y: 85
        }
    });
};

export function showErrors(error) {
    for (let msg of error.messages.values()) {
        notify(msg, 'danger');
    }
}
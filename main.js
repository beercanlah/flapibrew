// We make heavy use of the following tutorial on websockets
// http://blog.new-bamboo.co.uk/2010/02/10/json-event-based-convention-websockets

/* Ismael Celis 2010
Simplified WebSocket events dispatcher (no channels, no users)

var socket = new FancyWebSocket();

// bind to server events
socket.bind('some_event', function(data){
  alert(data.name + ' says: ' + data.message)
});

// broadcast events to all connected users
socket.send( 'some_event', {name: 'ismael', message : 'Hello world'} );
*/

var FancyWebSocket = function(url) {
    var conn = new WebSocket(url);

    var callbacks = {};

    this.bind = function(event_name, callback) {
	callbacks[event_name] = callbacks[event_name] || [];
	callbacks[event_name].push(callback);
	return this;// chainable
    };

    this.send = function(event_name, event_data) {
	var payload = JSON.stringify({event:event_name, data: event_data});
	conn.send( payload ); // <= send JSON data to socket server
	return this;
    };

    this.close = function() {
	conn.close();
    };

    // dispatch to the right handlers
    conn.onmessage = function(evt) {
	var json = JSON.parse(evt.data);
	dispatch(json.event, json.data);
    };

    conn.onclose = function() {
	dispatch('close',null);
    };

    conn.onopen = function() {
	dispatch('open',null);
    };

    var dispatch = function(event_name, message) {
	var chain = callbacks[event_name];
	if(typeof chain == 'undefined') return; // no callbacks for this event
	for(var i = 0; i < chain.length; i++){
	    chain[i]( message );
	}
    };
};

$(document).ready(function () {

    
    
    var ws;
    var socketOpen = false;
    
    $("#websocketConnection").click(function(evt) {
        evt.preventDefault();
	
        var url = "ws://127.0.0.1:5050/ws";
	
        if (!socketOpen) {
            ws = new FancyWebSocket(url);
	    
            ws.bind("close", function(evt) {
		$("#websocketConnection").css("background", "#ffffff");
		$("#websocketConnection").text("Open Websocket")
	    });
	    
            ws.bind("open", function(evt) { 
		$("#websocketConnection").css("background", "#00ff00");
		$("#websocketConnection").text("Close Websocket");
            });

            socketOpen = true;
        } // end if (!socketOpen)
        else
        {
            ws.close();
            socketOpen = false;
        }
    });
    
    // Request an image
    $("#requestImage").click(function(evt) {
        evt.preventDefault();
        ws.send('Image');
    });
});
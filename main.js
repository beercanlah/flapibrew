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
	console.log(payload);
	conn.send( payload ); // <= send JSON data to socket server
	return this;
    };

    this.close = function() {
	conn.close();
    };

    // dispatch to the right handlers
    conn.onmessage = function(evt) {
	var json = JSON.parse(evt.data);
	console.log(json);
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

    var breweryState = {
	pumpOn: false,
	recordingData: false
    };
    
    var ws;
    var url = "ws://127.0.0.1:5050/ws";
	
    ws = new FancyWebSocket(url);
    
    ws.bind("close", function(data) {
	$("#websocketConnection").css("background", "#ffffff");
	$("#websocketConnection").text("Open Websocket");
    });
    
    ws.bind("open", function(data) { 
	$("#websocketConnection").css("background", "#00ff00");
	$("#websocketConnection").text("Close Websocket");
    });

    ws.bind("plot_update", function(data) {
	$("#plot").attr("src", data.img_string);
    });

    ws.bind("status_update", function(data) {
	$("#temperature").text(data.temperature);
	$("#pumpState").text(data.pump_state);
	$("#heaterState").text(data.heater_state);
	$("#PIDState").text(data.pid_state);
    });
    
    // Request an image
    $("#plotting").click(function(evt) {
        evt.preventDefault();
	if (!breweryState.recordinData) {
	    ws.send('backend', {'port': 'dummy'});
	    ws.send('plot_request', {'state': 'on'});
	}
    });
});

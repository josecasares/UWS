var socket=null

$(document).ready(function(){
	
	/* Carga estilos y librerías auxiliares */
	$("head").append($("<link rel='stylesheet' type='text/css' href='uws/c.css'>"));
	$("head").append($("<link rel='stylesheet' type='text/css' href='uws/jquery.datetimepicker.css'>")); 
	$("head").append($("<script type='text/javascript' src='uws/jquery.flot.js'>"));
	$("head").append($("<script type='text/javascript' src='uws/jquery.flot.time.js'>"));
	$("head").append($("<script type='text/javascript' src='uws/jquery.datetimepicker.js'>"));

	/* Asocia eventos a elementos dinámicos */
	events();

	/* Abre socket de comunicación con servidor */
	host=window.location.host.split(":")[0];
	port=8083;
	socket = new WebSocket("ws://"+host+":"+port);
	socket.onopen = function(){
		register();
		trend_init();
	};
	
	/* Gestión de mensajes recibidos */
	socket.onmessage = function(data){
		data=JSON.parse(data.data);
		/* Actualización de variables */
		if (data["action"]==="values") {
			tags=data["tags"];
			tags.forEach(function(pair) {
				key=pair[0];
				value=pair[1];
				$("[data-dir='"+key+"']").each(function () {
					handler=$(this);
					value=transformation(value,handler.attr("data-transform"));
					if (handler.attr("data-css")!==undefined) 
						handler.css(handler.attr("data-css"), value);
					else {
						if (handler.is("input:text")) {
							if (!handler.is(":focus"))
								handler.val(value);
						}
						if (handler.is("input:checkbox")) {
							handler.prop("checked",value=="True");
						}
						if (handler.is("p") || handler.is("span")) {
							handler.html(value);
						}
						if (handler.is("div")) {
							if (value=="True") handler.show();
							else handler.hide();
						}
					}
				});
			});
		}
		
		/* Actualización de alarmas */
		if (data["action"]==="alarms") {
			alarms=data["alarms"];
			alarms.forEach(function(pair) {
				key=pair[0];
				timestamp=getlocaltime(pair[1]);
				description=pair[2];
				state=pair[3];
				alarmgroup=pair[4];
				$("[data-alarmgroup='"+alarmgroup+"']").each(function () {
					handler=$(this);
					historical=($(this).attr("data-historical")!==undefined);
					tr=handler.find("[data-key='"+key+"']");
					if ((state=="True" && tr.length==0) || historical) {
						if (state=="True")
							decoration="alarm-active";
						else
							decoration="alarm-inactive";
						if (handler.find("tbody tr").length>=getmaxalarms(handler))
							handler.find("tbody tr:last").remove();
						content="<tr data-key='"+key+"' data-state='"+state+"' class='"+decoration+"'><td>"+timestamp+"</td><td>"+state+"</td><td>"+description+"</td></tr>";
						handler.find("tbody").prepend($(content));
					}
					if ((state=="False" && tr.length>0) && !historical) {
						handler.find("[data-key='"+key+"']").remove();
					}
					if ((state=="False" && tr.length>0) && historical) {
						handler.find("[data-key='"+key+"'][data-state='True']").attr("class","alarm-past");
					}
				});
			});
		}
		
		/* Actualización de tendencias */
		if (data["action"]==="trend") {
			trend=data["trend"];
			//datefrom=getdatetime(data["from"]);
			//dateto=getdatetime(data["to"]);
			tags=data["tags"];
			options={ xaxis: { mode: "time", timeformat: "%d/%m/%Y %H:%M:%S" }};
			$.plot($("#"+trend), tags, options);
		}
	};
	
	/* Entradas de calendario */
	$("[data-datetime]").each(function() {
		$(this).width(120);
		$(this).datetimepicker({value:new Date(),step:60});
	});
		

});

/* Eventos de elementos dinámicos */
function events() {
	$("input[data-dir]").each(function(){
		
		if (!$(this).parents("form").length) {		// Si no está en un formulario
			/* Checkboxes (consignas digitales) */
			if ($(this).is("input:checkbox")) {
				$(this).change(function() {
					message={"action":"change",
						"tag":$(this).attr("data-dir"),
						"value":$(this).prop("checked")};
					socket.send(JSON.stringify(message));
				});		
			};
			
			/* Campos de texto (otro tipo de consignas) */
			if ($(this).is("input:text")) {
				$(this).change(function() {
					message={"action":"change",
						"tag":$(this).attr("data-dir"),
						"value":$(this).val()};
					socket.send(JSON.stringify(message));
				});
			};
		};
	});
	
	/* Formularios (inserciones en tablas) */
	$("[data-table]").each(function(){
		$(this).submit(function() {
			request={};
			request["action"]="set_row";
			request["date"]=$(this).find("[data-datetime]").val();
			tagrequest={};
			$(this).find("[data-dir]").each(function() {
				key=$(this).attr("data-dir");
				value=$(this).val();
				tagrequest[key]=value;
			});
			request["tags"]=tagrequest;
			data=JSON.stringify(request);
			socket.send(data);
			return false;		// Evita que se recargue la página
		});		
	});
}

/* Subscripción de variables */
function register() {
	request={};
	request["action"]="subscribe";
	
	tagrequest=[];
	$("[data-dir]").each(function() {
		key=$(this).attr("data-dir");
		if ($.inArray(key,tagrequest))
			tagrequest.push(key);
	});
	if (tagrequest.length>0)
		request["tags"]=tagrequest;

	alarmgrouprequest=[];
	$("[data-alarmgroup]").each(function() {
		handler=$(this);
		key=handler.attr("data-alarmgroup");
		maxalarms=getmaxalarms(handler);
		for(i=1;i<maxalarms;i++) {
			content="<tr><td>&nbsp;</td><td></td><td></td></tr>";
			handler.find("tbody").append(content);
		}
		elem=key.split(";").forEach(function(str) {
			if ($.inArray(str,alarmgrouprequest))
				alarmgrouprequest.push(str);
		});	
	});
	if (alarmgrouprequest.length>0)
		request["alarmgroups"]=alarmgrouprequest;	
	
	data=JSON.stringify(request);
	socket.send(data);
}

/* Actualización de tendencias */
function trend_init() {
	controls_html="<input type='button' value='<<<'/> <input type='button' value='<<'/> <input type='button' value='<'/> <input type='button' value='-> <-'/><input type='button' value='Now'/> <input type='button' value='<-->'/> <input type='button' value='>'/> <input type='button' value='>>'/> <input type='button' value='>>>'/>";
	
	$("[data-trend]").each(function() {
		request={};
		request["action"]="trend";
		
		id=$(this).attr("id");
		trend=id+"-trend";
		controls=id+"-controls";
		request["trend"]=trend;
		$(this).append("<div id='"+trend+"'></div>");
		$(this).append("<div id='"+controls+"'></div>");
		_trend=$("#"+trend);
		_controls=$("#"+controls);
		_trend.height($(this).height()-20);
		_trend.width($(this).width());
		_controls.append(controls_html).children().each(function () {
			$(this).click(trendcontrol);
		});
		
		today = (new Date()).getTime();
		yesterday = today-1000*60*60*24;
		$(this).attr("data-from",yesterday);
		$(this).attr("data-to",today);
		
		trend_update(id);	
	});
}

function trend_update(id) {
		request["from"]=$("#"+id).attr("data-from");
		request["to"]=$("#"+id).attr("data-to");
		
		tags=[]
		$("#"+id).attr("data-trend").split(";").forEach(function(str) {
			tags.push(str);
		});	
		request["tags"]=tags;
		data=JSON.stringify(request);
		socket.send(data);
}

function trendcontrol() {
	id=$(this).parent().parent().attr("id");
	_from=parseInt($("#"+id).attr("data-from"));
	_to=parseInt($("#"+id).attr("data-to"));
	interval=_to-_from;
	
	switch($(this).attr("value")) {
		case "<<<":
			_from=_from-interval;
			_to=_from+interval;
			break;
		case "<<":
			_from=_from-interval/2;
			_to=_from+interval;
			break;
		case "<":
			_from=_from-interval/4;
			_to=_from+interval;
			break;
		case "-> <-":
			_from=_from+interval/4;
			interval=interval/2;
			_to=_from+interval;
			break;
		case "Now":
			_to=(new Date()).getTime();
			break;
		case "<-->":
			_from=_from-interval/2;
			interval=interval*2;
			_to=_from+interval;
			break;
		case ">":
			_from=_from+interval/4;
			_to=_from+interval;
			break;
		case ">>":
			_from=_from+interval/2;
			_to=_from+interval;
			break;
		case ">>>":
			_from=_from+interval;
			_to=_from+interval;
			break;
	}
	$("#"+id).attr("data-from",_from);
	$("#"+id).attr("data-to",_to);
	trend_update(id);
}


function transformation(data,transformations) {
	if (transformations!==undefined) {
		transformations.split(";").forEach(function(operation) {
			item=operation.split(":");
			switch(item[0]) {
				case "invert": 
					if (data=="True") data="False";
					else data="True";
					break;
				case "scale":
					coordinate=item[1].split(",");
					data=parseFloat(data);
					x0=parseFloat(coordinate[0]);
					x1=parseFloat(coordinate[1]);
					y0=parseFloat(coordinate[2]);
					y1=parseFloat(coordinate[3]);
					data=data/(x1-x0)*(y1-y0)+y0;
			};
		});
	}
	return data;
}

function getmaxalarms(handler) {
	datamaxalarms=handler.attr("data-maxalarms");
	if (datamaxalarms==undefined) 
		maxalarms=0;
	else
		maxalarms=parseInt(datamaxalarms);
	if (maxalarms==0) maxalarms=3;
	return maxalarms;
}

function getlocaltime(timestamp) {
	if (timestamp=="")
		return "";
	else
		return (new Date(timestamp+" UTC")).toLocaleString();;
}

function getdatetime(datetime) {
	return datetime.getFullYear()+"-"+(datetime.getMonth()+1)+"-"+datetime.getDate()+" "+datetime.getHours()+":"+datetime.getMinutes();
}
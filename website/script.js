window.sheet_template = null;

function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function renderhealth(health_text, max_value)
{
	if (max_value <= 0)
	{	
		var health_render = document.createElement('p');
		health_render.innerHTML = "N/A";
		return health_render;
	}
	
	hurt_levels_vampire = ["Illeso (0)", "Contuso (0)", "Graffiato (-1)",	"Leso (-1)", "Ferito (-2)", "Straziato (-2)", "Menomato (-5)",	"Incapacitato"];
	
	var img_map = new Map([
	   ['a', 'hl_aggravated.png'],
	   ['l', 'hl_lethal.png'],
	   ['c', 'hl_bashing.png'],
	   [' ', 'hl_free.png'],
	   ['B', 'hl_blocked.png']
	]);
	
	var health_render = document.createElement('table');
	charsheet.setAttribute("class", 'w3-table');
	
	var hs = health_text;
    hs = hs + (" ".repeat(max_value-hs.length));
    var levels = hurt_levels_vampire.length - 1 ;
    var columns = Math.floor(hs.length / levels )
    var extra = hs.length % levels;
    var width = columns + (extra > 0);
    var cursor = 0;
    var health_lines = [];
	var i;
    for (i = 0; i < levels; ++i)
	{
		var line = document.createElement('tr');
		
		var level = document.createElement('td');
		level.setAttribute("class", "nopadding");
		level.innerHTML = hurt_levels_vampire[i];
		line.appendChild(level);
        
		var j;
		var add;
		if (i < extra)
		{
			add = width;
		}
		else
		{
			add = columns;
		}
		for (j=cursor; j<(cursor+add); ++j)
		{
			var cell = document.createElement('td');
			cell.setAttribute("class", "nopadding");
			console.log(hs[j]);
			cell.innerHTML = '<img height="20" width="20" class = "w3-border" src="../img_res/'+img_map.get(hs[j])+'" />';
			line.appendChild(cell);
		}
		if (extra > 0 && i >= extra)
		{
			var cell = document.createElement('td');
			cell.setAttribute("class", "nopadding");
			console.log(hs[j]);
			cell.innerHTML = '<img height="20" width="20" class = "w3-border" src="../img_res/'+img_map.get("B")+'" />';
			line.appendChild(cell);
		}
		cursor += add;
		health_render.appendChild(line);
	}
	return health_render;
}

function populateSheet(characterTraits, character){
	// create new sheet
	var charsheet = window.sheet_template.cloneNode(true);
	charsheet.setAttribute("id", 'charsheet');
	// insert new sheet
	var main = document.getElementById('main_content');
	main.appendChild(charsheet);
	// do stuff
	document.getElementById('title_pgname').innerHTML = '<b>'+character.fullname+'</b>';
	//charsheet.innerHTML = '';
	var temp_dump = document.getElementById('temp_dump');
	temp_dump.innerHTML = '';
	var dot = "&#9899;"; //"⚫"; //9899
	var emptydot = "&#9898;"; //"⚪"; //9898
	var red_dot = "&#128308;";
	var blue_dot = "&#128309;";
	var square_full = "&#11035;"
	var square_empty = "&#11036;"
	var i;
	var switches = new Map([
	   ['viataum', true],
	   ['vianecro', true],
	   ['combinata', true],
	   ['talento', true],
	   ['viaduranki', true],
	   ['viaahku', true],
	   ['viadarktaum', true],
	   ['brujerizmo', true]
	]);
	
	var generation = -1;
	
    for (i = 0; i<characterTraits.length; ++i){
		traitdata = characterTraits[i];
		if (switches.get(traitdata.traittype)){
			switches.set(traitdata.traittype, false);
		}
		var sheetspot = document.getElementById(traitdata.traittype);
		if (sheetspot)
		{
			var c = document.createElement('tr'); 
			c.setAttribute("id", traitdata.trait);
			// tratti con visualizzazioni specifiche
			if (traitdata.trait == 'volonta')
			{
				c.innerHTML = '<h4>Forza di Volontà</h4><p>'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 10-traitdata.max_value))+'</p><p>'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, 10-traitdata.cur_value))+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.trait == 'sangue')
			{
				c.innerHTML = '<h4>Punti Sangue</h4><p>'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, traitdata.max_value-traitdata.cur_value))+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.trait == 'umanita')
			{
				c.innerHTML = '<h4>Umanità</h4><p>'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 10-traitdata.max_value))+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.trait == 'exp')
			{
				c.innerHTML = '<p>'+traitdata.name+': '+traitdata.cur_value+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.trait == 'salute')
			{
				c.appendChild(renderhealth(traitdata['text_value'], traitdata['max_value']));
			}
			// tratti std
			else if (!traitdata.textbased)
			{
				var tname = traitdata.name;
				if (!traitdata.standard && (['attitudine', 'capacita', 'conoscenza'].indexOf(traitdata.traittype) >= 0 ))
				{
					tname = '<b>'+tname+'</b>';
				}
				//c.innerHTML = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding">'+(dot.repeat(traitdata.cur_value))+emptydot.repeat(Math.max(0, 5-traitdata.cur_value))+"</td>";
				//c.innerHTML = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding">'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 5-traitdata.max_value))+"</td>";
				var temp = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding">'+dot.repeat(Math.min(traitdata.cur_value,traitdata.max_value));
				if (traitdata.cur_value < traitdata.max_value)
					temp += red_dot.repeat(traitdata.max_value-traitdata.cur_value)
				if (traitdata.cur_value>traitdata.max_value)
					temp += blue_dot.repeat(traitdata.cur_value-traitdata.max_value)
				max_dots = Math.max(traitdata.pimp_max, 5)
				if (traitdata.cur_value < max_dots)
					temp += emptydot.repeat(max_dots-Math.max(traitdata.max_value, traitdata.cur_value));
				temp += "</td>"
				c.innerHTML = temp;
			}
			else
			{
				var temp = traitdata.name
				if (traitdata.text_value != "-"){
					temp += ": "+ traitdata.text_value;
				}
				c.innerHTML = temp;
			}
			sheetspot.appendChild(c);
			if (traitdata.trait == 'generazione')
			{
				generation = 13-traitdata.max_value;
			}
		}
		else
		{
			var c = document.createElement('p');
			//c.innerHTML = menuItem;
			//c = c.firstChild
			c.setAttribute("id", traitdata.trait);
			c.innerHTML = traitdata.name + ": " + traitdata.cur_value + "/" + traitdata.max_value + " " +traitdata.text_value;
			temp_dump.appendChild(c);
			//c.addEventListener('click', function(id){var cid = id; return function() {load_charSheet(cid);}}(character.id))
		}
	}
	// generazione
	var sheetspot = document.getElementById("testata");
	var c = document.createElement('tr'); 
	c.setAttribute("id", "generazione_calcolata");
	c.innerHTML = generation+"a Generazione"
	sheetspot.appendChild(c);
	// pegni blocchi ventaggi vuoti
	for (var key of switches.keys()) {
		if (switches.get(key))
		{
			var temp = document.getElementById('switch_'+key);
			temp.remove();
		}
	}
	var central_msg = document.getElementById('central_msg');
	central_msg.style.display = "none";
	charsheet.style.display = "inline";
}

function load_charSheet(character){
	var charsheet = document.getElementById('charsheet');
	if (charsheet)
	{
		charsheet.remove();
	}
	var central_msg = document.getElementById('central_msg');
	central_msg.innerHTML = '<i class="fa fa-refresh"></i>';
	central_msg.style.display = "inline";
	get_remote_resource('./getCharacterTraits?charid='+character.id, 'json', function(data){populateSheet(data, character)});
}

function populate_charmenu(menuItem, chars){
	var side_menu = document.getElementById('side_menu');
	var i;
    for (i = 0; i<chars.length; ++i){
		character = chars[i];
        var c = document.createElement('div');
        c.innerHTML = menuItem;
		c = c.firstChild
		c.setAttribute("id", character.id);
		c.innerHTML = character.fullname
        side_menu.appendChild(c);
		c.addEventListener('click', function(chardata){var c = chardata; return function() {load_charSheet(c);}}(character))
	}
}

function get_remote_resource(url, res_type, callback){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = res_type;
    xhr.onload = function() {
      var status = xhr.status;
      if (status === 200) {
        callback(xhr.response);
      } else {
        //callback(status, xhr.response);
        console.log('Error ('+status+') while getting remote resource '+url);
        post_error(status);
      }
    };
    xhr.send();
}

function post_error(text){
    //updateStatus('Error!');
    //var main = document.getElementById('main');
    //var alertPanel = document.createElement('div');
    //alertPanel.innerHTML = '<div class="w3-panel w3-red">  <h3>Danger!</h3>  <p>'+text+'</p></div>';
    //main.appendChild(alertPanel);
	alert(text);
}

function populate_page(){
	window.sheet_template = document.getElementById('charsheet_template');
	window.sheet_template.remove();
    //var side_menu = document.getElementById('side_menu');
    get_remote_resource('./getMyCharacters', 'json',  getCharMenuItem);
}
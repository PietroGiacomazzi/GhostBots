window.sheet_template = null;
window.selected_charid = null;
window.language_dictionary = null;
var urlParams = new URLSearchParams(window.location.search);

if (!String.format) {
	String.format = function(format) {
	  var args = Array.prototype.slice.call(arguments, 1);
	  return format.replace(/{(\d+)}/g, function(match, number) { 
		return typeof args[number] != 'undefined'
		  ? args[number] 
		  : match
		;
	  });
	};
  }

function getLangString(string_id){
	if (window.language_dictionary){
		return window.language_dictionary[string_id]
	}
	else
	{
		return string_id;
	}
}

function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function getMyCharacters(dictionary){
	window.language_dictionary = dictionary;
    get_remote_resource('./getMyCharacters', 'json',  getCharMenuItem);
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
	
	/*
	//extra line for "healthy"
	var line = document.createElement('tr');
	var level = document.createElement('td');
	level.setAttribute("class", "nopadding");
	level.innerHTML = hurt_levels_vampire[0];
	line.appendChild(level);
	var cell = document.createElement('td');
	cell.innerHTML = '<span/>';
	line.appendChild(cell);
	health_render.appendChild(line);
	*/
	
    for (i = 0; i < levels; ++i)
	{
		var line = document.createElement('tr');
		
		var level = document.createElement('td');
		level.setAttribute("class", "nopadding");
		level.innerHTML = hurt_levels_vampire[i+1];
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
			//console.log(hs[j]);
			cell.innerHTML = '<img height="20" width="20" class = "w3-border" src="../img_res/'+img_map.get(hs[j])+'" />';
			line.appendChild(cell);
		}
		if (extra > 0 && i >= extra)
		{
			var cell = document.createElement('td');
			cell.setAttribute("class", "nopadding");
			//console.log(hs[j]);
			cell.innerHTML = '<img height="20" width="20" class = "w3-border" src="../img_res/'+img_map.get("B")+'" />';
			line.appendChild(cell);
		}
		cursor += add;
		health_render.appendChild(line);
	}
	return health_render;
}

function render_clan_icon(icon_path){
	//console.log("owo:"+icon_path.clan_icon);
	if (icon_path.clan_icon)
	{
		el = document.getElementById('title_clanicon');
		el.src = icon_path.clan_icon;
		el.width=icon_path.icon_size;
		//el.height="100";
	}
}

function populate_clan_img(clan_name){
	get_remote_resource('./getClanIcon?clan='+clan_name, 'json', render_clan_icon);
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
	
	// nome del giocatore
	sheetspot = document.getElementById("testata");
	var c = document.createElement('tr'); 
	c.setAttribute("id", 'nome_giocatore');
	c.innerHTML = String.format(getLangString("web_string_charplayer"), character.ownername); 
	sheetspot.appendChild(c);
	
	//charsheet.innerHTML = '';
	var temp_dump = document.getElementById('altro');
	temp_dump.style.display = "none";
	//temp_dump.innerHTML = '';
	var dot = "&#9899;"; //"⚫"; //9899
	var emptydot = "&#9898;"; //"⚪"; //9898
	var red_dot = "&#128308;";
	var blue_dot = "&#128309;";
	var square_full = "&#11035;"
	var square_empty = "&#11036;"
	var i;
	var switchesFree = new Map([
	   ['combinata', true],
	   ['talento', true]	
	]);
	var switchesVie = new Map([
	   ['viataum', true],
	   ['vianecro', true],
	   ['viaduranki', true],
	   ['viaahku', true],
	   ['viadarktaum', true],
	   ['brujerizmo', true]
	]);
	var global_switches_vie = true;
	
	
	var generation = -1;
	
    for (i = 0; i<characterTraits.length; ++i){
		traitdata = characterTraits[i];
		if (switchesFree.get(traitdata.traittype)){
			switchesFree.set(traitdata.traittype, false);
		}
		if (switchesVie.get(traitdata.traittype)){
			switchesVie.set(traitdata.traittype, false);
			global_switches_vie = false;
		}
		var sheetspot = document.getElementById(traitdata.traittype);
		if (sheetspot)
		{
			var c = document.createElement('tr'); 
			c.setAttribute("id", traitdata.trait);
			// tratti con visualizzazioni specifiche
			if (traitdata.trait == 'volonta')
			{
				c.innerHTML = '<h4>'+getLangString("web_label_willpower")+'</h4><p>'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 10-traitdata.max_value))+'</p><p>'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, 10-traitdata.cur_value))+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.trait == 'sangue')
			{
				c.innerHTML = '<h4>'+getLangString("web_label_bloodpoints")+'</h4><p>'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, traitdata.max_value-traitdata.cur_value))+'</p>'; // todo elemento a parte?
			}
			/*
			else if (traitdata.trait == 'umanita')
			{
				c.innerHTML = '<h4>Umanità</h4><p>'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 10-traitdata.max_value))+'</p>'; // todo elemento a parte?
			}*/
			else if (traitdata.trait == 'salute')
			{
				c.appendChild(renderhealth(traitdata['text_value'], traitdata['max_value']));
			}
			else if (traitdata.trait == 'exp')
			{
				c.innerHTML = '<p>'+traitdata.tnameLang+': '+traitdata.cur_value+'</p>'; // todo elemento a parte?
			}
			else if (traitdata.traittype == 'uvp'){
				if (traitdata.trackertype == 0) // normale
				{
					c.innerHTML = '<h4>'+traitdata.tnameLang+'</h4><p>'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 10-traitdata.max_value))+'</p>';
				}
				else if (traitdata.trackertype == 1) // punti con massimo
				{
					c.innerHTML = '<h4>'+traitdata.tnameLang+'</h4><p>'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, traitdata.max_value-traitdata.cur_value))+'</p>';
				}
				else if (traitdata.trackertype == 2) // danni
				{
					c.innerHTML = '<h4>'+traitdata.tnameLang+'</h4><p>'+traitdata.text_value+' (non implementato)</p>'; // TODO
				}
				else if (traitdata.trackertype == 3) // punti senza massimo
				{
					c.innerHTML = '<h4>'+traitdata.tnameLang+': '+traitdata.cur_value+'</h4>';
				}
				else //fallback
				{
					c.innerHTML = '<h4>'+traitdata.tnameLang+'</h4><p>'+ traitdata.cur_value + "/" + traitdata.max_value + " " +traitdata.text_value+'</p>'; 
				}
			}
			// tratti std
			else if (!traitdata.textbased)
			{
				var tname = traitdata.tnameLang;
				if (!traitdata.standard && (['attitudine', 'capacita', 'conoscenza'].indexOf(traitdata.traittype) >= 0 ))
				{
					tname = '<b>'+tname+'</b>';
				}
				
				if (traitdata.trackertype == 0) // normale
				{
					//c.innerHTML = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding">'+(dot.repeat(traitdata.cur_value))+emptydot.repeat(Math.max(0, 5-traitdata.cur_value))+"</td>";
					//c.innerHTML = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding">'+(dot.repeat(traitdata.max_value))+emptydot.repeat(Math.max(0, 5-traitdata.max_value))+"</td>";
					var temp = '<td class="nopadding">'+tname+ ": " +"</td>" +'<td class="nopadding" style="float:right">'+dot.repeat(Math.min(traitdata.cur_value,traitdata.max_value));
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
				else if (traitdata.trackertype == 1) // punti con massimo
				{
					c.innerHTML = '<td class="nopadding">'+tname+ "</td>" +'<td class="nopadding" style="float:right">'+(square_full.repeat(traitdata.cur_value))+square_empty.repeat(Math.max(0, traitdata.max_value-traitdata.cur_value))+'</td>';
				}
				else if (traitdata.trackertype == 2) // danni
				{
					c.innerHTML = '<td class="nopadding">'+tname +"</td>" +'<td class="nopadding" style="float:right">'+traitdata.text_value+' (non implementato)'+'</td>';// TODO
				}
				else if (traitdata.trackertype == 3) // punti senza massimo
				{
					c.innerHTML = '<td class="nopadding">'+tname +"</td>" +'<td class="nopadding" style="float:right">'+traitdata.cur_value+'</td>';
				}
				else //fallback
				{
					c.innerHTML = '<td class="nopadding">'+tname+"</td>" +'<td class="nopadding" style="float:right">'+ traitdata.cur_value + "/" + traitdata.max_value + " " +traitdata.text_value+'</td>';
				}
			}
			else
			{
				var temp = traitdata.tnameLang
				if (traitdata.text_value != "-"){
					temp += ": "+ traitdata.text_value;
				}
				c.innerHTML = temp;
				if (traitdata.trait == 'clan')
				{
					populate_clan_img(traitdata.text_value);
				}
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
			if (temp_dump.style.display == 'none')
			{
				temp_dump.style.display = 'inline';
			}
			c.setAttribute("id", traitdata.trait);
			c.innerHTML = traitdata.tnameLang + ": " + traitdata.cur_value + "/" + traitdata.max_value + " " +traitdata.text_value;
			temp_dump.appendChild(c);
			//c.addEventListener('click', function(id){var cid = id; return function() {load_charSheet(cid);}}(character.id))
		}
	}
	// generazione
	var sheetspot = document.getElementById("testata");
	var c = document.createElement('tr'); 
	c.setAttribute("id", "generazione_calcolata");
	c.innerHTML = String.format(getLangString("web_string_calc_generation"), generation); 
	sheetspot.appendChild(c);
	// spegni blocchi ventaggi vuoti
	for (var key of switchesFree.keys()) {
		if (switchesFree.get(key))
		{
			var temp = document.getElementById('switch_'+key);
			temp.remove();
		}
	}
	for (var key of switchesVie.keys()) {
		if (switchesVie.get(key))
		{
			var temp = document.getElementById('switch_'+key);
			temp.remove();
		}
	}
	if (global_switches_vie){
		var temp = document.getElementById('switch_vie');
		temp.remove();
	}
	window.selected_charid = character.id;
	var modregisterbtn = document.getElementById('modregister');
	modregisterbtn.style.display = "inline";
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
	var loaded = urlParams.get('character') == null;
	var side_menu = document.getElementById('side_menu');
	if (chars.length)
	{
		var title = document.createElement('h3');
		title.innerHTML = "<h3>"+getLangString("web_label_chronicles")+":</h3>";
		side_menu.appendChild(title);
	}
	var i;
    for (i = 0; i<chars.length; ++i){
		character = chars[i];
		container_id = 'chronicle_container_'+character.chronichleid;
		var chronicle_container =  document.getElementById(container_id);
		if (chronicle_container == null)
		{
			var cc = document.createElement('div');
			
			var btn = document.createElement('button');
			btn.className = "w3-button w3-block w3-left-align";
			var chronicleName = character.chroniclename;
			if (chronicleName == null)
			{
				chronicleName = getLangString("web_label_no_chronicle_pcs");
			}
			btn.innerHTML = chronicleName + '&nbsp;<span class="material-icons md-18">arrow_drop_down</span>';
			btn.addEventListener('click', function(chid){var c = chid; return function() {accordionSwitch(c);}}(container_id));
			cc.appendChild(btn);
			
			chronicle_container = document.createElement('div');
			chronicle_container.id = container_id;
			chronicle_container.className = "w3-container w3-hide";
			cc.appendChild(chronicle_container);
			
			side_menu.appendChild(cc);
		}
        var c = document.createElement('div');
        c.innerHTML = menuItem;
		c = c.firstChild
		c.setAttribute("id", character.id);
		c.innerHTML = character.fullname
        chronicle_container.appendChild(c);
		c.addEventListener('click', function(chardata){var c = chardata; return function() {load_charSheet(c);}}(character))
		// load the character if needed:
		if (character.id === urlParams.get('character'))
		{
			load_charSheet(character);
			loaded = true;
		}
	}
	if (!loaded)
	{
		post_error( String.format(getLangString("web_string_no_access_to_pc"), urlParams.get('character')) );
	}
}

function view_modlog(content)
{
	if (content)
	{
		var logarea = document.getElementById('modlog_area');
		logarea.innerHTML = content;
		document.getElementById('modlog_modal').style.display = 'block';
	}
}

function accordionSwitch(id) {
  var x = document.getElementById(id);
  if (x.className.indexOf("w3-show") == -1) {
    x.className += " w3-show";
  } else {
    x.className = x.className.replace(" w3-show", "");
  }
}

function load_modlog()
{
	get_remote_resource('./getCharacterModLog?charid='+window.selected_charid, 'text',  view_modlog);
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
        post_error(status+": "+xhr.response);
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
	var modlog = document.getElementById('modregister');
	modlog.addEventListener('click', load_modlog);
    //var side_menu = document.getElementById('side_menu');
	get_remote_resource('./getLanguageDictionary', 'json', getMyCharacters)
}
window.sheet_template = null;

function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function populateSheet(characterTraits, character){
	// create new sheet
	var charsheet = window.sheet_template.cloneNode(true);
	charsheet.setAttribute("id", 'charsheet');
	//delete old sheet
	/*var old_cs = document.getElementById('charsheet');
	if (old_cs)
	{
		old_cs.remove();
	}*/
	// insert new sheet
	var main = document.getElementById('main_content');
	main.appendChild(charsheet);
	// do stuff
	document.getElementById('title_pgname').innerHTML = '<b>'+character.fullname+'</b>';
	//charsheet.innerHTML = '';
	var temp_dump = document.getElementById('temp_dump');
	temp_dump.innerHTML = '';
	var dot = "⚫";
	var emptydot = "⚪";
	var square_full = "&#11035;"
	var square_empty = "&#11036;"
	var i;
	var switches = new Map([
	   ['viataum', true],
	   ['vianecro', true],
	   ['combinata', true],
	   ['talento', true],
	   ['viaduranki', true]
	]);
	
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
			else if (!traitdata.textbased)
			{
				var tname = traitdata.name;
				if (!traitdata.standard && (['attitudine', 'capacita', 'conoscenza'].indexOf(traitdata.traittype) >= 0 ))
				{
					tname = '<b>'+tname+'</b>';
				}
				c.innerHTML = '<td>'+tname+ ": " +"</td>" +'<td>'+(dot.repeat(traitdata.cur_value))+emptydot.repeat(Math.max(0, 6-traitdata.cur_value))+"</td>";
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
window.sheet_template = null;
window.selected_charid = null;
window.language_dictionary = null;
window.dot_data = {
	dot: "&#9899;", //"⚫"; //9899
	emptydot: "&#9898;", //"⚪"; //9898
	red_dot: "&#128308;",
	blue_dot: "&#128309;",
	square_full: "&#11035;",
	square_empty: "&#11036;",
};
var urlParams = new URLSearchParams(window.location.search);

window.charEditMode = false;
window.editElements = Array();
window.traitList = null;
window.input_modal = null;

var replace_HTMLElement = [];
replace_HTMLElement['&'] = '&amp;';
replace_HTMLElement['<'] = '&lt;';
replace_HTMLElement['>'] = '&gt;';
replace_HTMLElement['"'] = '&quot;';
replace_HTMLElement["'"] = '&#x27;';

//var replace_HTMLattribute = []
//replace_HTMLattribute

function out_sanitize(string, sanitization_array = replace_HTMLElement){
	var final_string = string.toString();
	for (var key in sanitization_array) {
		final_string = final_string.replaceAll(key, sanitization_array[key]);
	}
	return final_string;
}

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
	// output sanitization is a bit overkill here
	if (window.language_dictionary){
		return out_sanitize(window.language_dictionary[string_id], replace_HTMLElement)
	}
	else
	{
		return out_sanitize(string_id, replace_HTMLElement);
	}
}

function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function getMyCharacters(dictionary){
	window.language_dictionary = dictionary;
    get_remote_resource('./getMyCharacters', 'json',  getCharMenuItem);
}

function openNewTrait(){
	if (window.charEditMode && window.input_modal != null  && window.traitList != null ){
		// inject the modal
		var modal_area = document.getElementById('inputmodal_area');	
		modal_area.innerHTML = window.input_modal

		var modal = document.getElementById('input_modal')
		modal.style.display = 'block';
		// setup the modal
		document.getElementById('input_modal_title').innerHTML = getLangString("web_label_add_trait");
		var form = document.getElementById('input_modal_form');
		//form.action = "./TODO"; // todo
		var input_tag = document.getElementById('input_modal_myInput');
		input_tag.setAttribute("placeholder", getLangString("web_label_trait")+"...");

		var input_save = document.getElementById('input_modal_submit');
		input_save.innerHTML = getLangString("web_label_save");
		input_save.addEventListener('click', function(event){
			var inp = document.getElementById('input_modal_myInput');
			// todo post
			const params = new URLSearchParams({
				traitId: inp.value,
				charId: window.selected_charid
			});
			get_remote_resource('./editCharacterTraitAdd?'+params.toString(), 'json', 
			function (traitdata){
				var sheetspot = document.getElementById(traitdata.traittype);
				if (sheetspot)
				{
					var c = createTraitElement(traitdata);
					sheetspot.appendChild(c);
				}
			}/*, 
			function(xhr){
			}*/)
			modal.style.display='none';
			modal.remove();
		 });

		autocomplete(document.getElementById("input_modal_myInput"), window.traitList);
	}
	else{
		console.log("not yet!");
	}
}

function enableCharEditMode(){
	if (window.input_modal == null){
		get_remote_resource('../html_res/InputFieldModal.html', 'text',  function(modaldata){window.input_modal = modaldata;});
	}
	if (window.traitList == null){
		get_remote_resource('./traitList', 'json', function(data){window.traitList = data});
	}

	var editcontrol = document.getElementById("editchar");
	editcontrol.innerHTML = getLangString("web_label_fihishedit_character");

	window.charEditMode = true;
	for (i = 0; i<window.editElements.length; ++i)
	{
		el = document.getElementById(window.editElements[i]);
		if (el == null){
			console.log(window.editElements[i])
		}
		else{
			el.style.display = 'inline';
		}
	}
}

function disableCharEditMode(){
	var editcontrol = document.getElementById("editchar");
	editcontrol.innerHTML = getLangString("web_label_edit_character");

	window.charEditMode = false;
	for (i = 0; i<window.editElements.length; ++i)
	{
		el = document.getElementById(window.editElements[i]);
		if (el == null){
			console.log(window.editElements[i])
		}
		else{
			el.style.display = 'none';
		}
	}
}

function switchEditMode(){
	if (window.charEditMode){
		disableCharEditMode();
	}
	else{
		enableCharEditMode()
	}
}

function renderhealth(health_text, max_value)
{
	if (max_value <= 0)
	{	
		var health_render = document.createElement('p');
		health_render.innerHTML = "N/A";
		return health_render;
	}
	
	hurt_levels_vampire = [
		getLangString("hurt_levels_vampire_unharmed"),
		getLangString("hurt_levels_vampire_bruised"),
		getLangString("hurt_levels_vampire_hurt"),
		getLangString("hurt_levels_vampire_injured"),
		getLangString("hurt_levels_vampire_wounded"),
		getLangString("hurt_levels_vampire_mauled"),
		getLangString("hurt_levels_vampire_crippled"),
		getLangString("hurt_levels_vampire_incapacitated")
	]
	
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
		level.className = "nopadding";
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
			cell.className = "nopadding";

			var img = document.createElement('img');
			img.setAttribute('height', "20");
			img.setAttribute('width', "20");
			img.className = "w3-border";
			img.src = '../img_res/'+img_map.get(hs[j]);
			cell.appendChild(img);
			line.appendChild(cell);
		}
		if (extra > 0 && i >= extra)
		{
			var cell = document.createElement('td');
			cell.className = "nopadding";

			var img = document.createElement('img');
			img.setAttribute('height', "20");
			img.setAttribute('width', "20");
			img.className = "w3-border";
			img.src = '../img_res/'+img_map.get("B");
			cell.appendChild(img);
			line.appendChild(cell);
		}
		cursor += add;
		health_render.appendChild(line);
	}
	return health_render;
}

function render_clan_icon(icon_path){
	if (icon_path.clan_icon)
	{
		el = document.getElementById('title_clanicon');
		el.src = icon_path.clan_icon;
		el.width=icon_path.icon_size;
	}
}

function populate_clan_img(clan_name){
	get_remote_resource('./getClanIcon?clan='+clan_name, 'json', render_clan_icon);
}

function editTrait(event) {
    var span = event.target;
	//console.log(span);
	if (window.charEditMode && span.dataset.traitid)
	{
		if (span.dataset.removetrait){
			// todo post
			const params = new URLSearchParams({
				traitId: span.dataset.traitid,
				charId: window.selected_charid
			});
			get_remote_resource('./editCharacterTraitRemove?'+params.toString(), 'json', 
			function (data){
				var oldTrait = document.getElementById(data.trait);
				oldTrait.remove();
			}/*, 
			function(xhr){
			}*/)
		}
		else if (!span.dataset.textbased){
			if (span.dataset.current_val){
				if (span.dataset.dotbased){
					// todo post
					const params = new URLSearchParams({
						traitId: span.dataset.traitid,
						charId: window.selected_charid,
						newValue: span.dataset.dot_id
					});
					get_remote_resource('./editCharacterTraitNumberCurrent?'+params.toString(), 'json', 
					function (data){
						var newTrait = createTraitElement(data);
						var oldTrait = document.getElementById(data.trait);
						oldTrait.parentNode.replaceChild(newTrait, oldTrait);
					}/*, 
					function(xhr){
					}*/)
				}
				else {
					editBox(event, 
						function (id){
							input_id = id+'-input'
							var input_tag = document.getElementById(input_id);
							// todo post
							const params = new URLSearchParams({
								traitId: span.dataset.traitid,
								charId: window.selected_charid,
								newValue: input_tag.value
							});
							get_remote_resource('./editCharacterTraitNumberCurrent?'+params.toString(), 'json', 
							function (data){
								var newTrait = createTraitElement(data);
								var oldTrait = document.getElementById(data.trait);
								oldTrait.parentNode.replaceChild(newTrait, oldTrait);
							}/*, 
							function(xhr){
							}*/)
						}
						, function (id){
							span.innerHTML = span.dataset.backup;
							span.dataset.editable = "1";
						}
						);
				}
			}
			else{
				if (span.dataset.dotbased){
					// todo post
					const params = new URLSearchParams({
						traitId: span.dataset.traitid,
						charId: window.selected_charid,
						newValue: span.dataset.dot_id
					});
					get_remote_resource('./editCharacterTraitNumber?'+params.toString(), 'json', 
					function (data){
						var newTrait = createTraitElement(data);
						var oldTrait = document.getElementById(data.trait);
						oldTrait.parentNode.replaceChild(newTrait, oldTrait);
					}/*, 
					function(xhr){
					}*/)
				}
				else{
					editBox(event, 
						function (id){
							input_id = id+'-input'
							var input_tag = document.getElementById(input_id);
							// todo post
							const params = new URLSearchParams({
								traitId: span.dataset.traitid,
								charId: window.selected_charid,
								newValue: input_tag.value
							});
							get_remote_resource('./editCharacterTraitNumber?'+params.toString(), 'json', 
							function (data){
								var newTrait = createTraitElement(data);
								var oldTrait = document.getElementById(data.trait);
								oldTrait.parentNode.replaceChild(newTrait, oldTrait);
							}/*, 
							function(xhr){
							}*/)
						}
						, function (id){
							span.innerHTML = span.dataset.backup;
							span.dataset.editable = "1";
						}
						);
				}
			}
		}
		else if (span.dataset.textbased){
			editBox(event, 
				function (id){
					input_id = id+'-input'
					var input_tag = document.getElementById(input_id);
					// todo post
					const params = new URLSearchParams({
						traitId: span.dataset.traitid,
						charId: window.selected_charid,
						newValue: input_tag.value
					});
					get_remote_resource('./editCharacterTraitText?'+params.toString(), 'json', 
					function (data){
						var newTrait = createTraitElement(data);
						var oldTrait = document.getElementById(data.trait);
						oldTrait.parentNode.replaceChild(newTrait, oldTrait);
					}/*, 
					function(xhr){
					}*/)
				}
				, function (id){
					span.innerHTML = span.dataset.backup;
					span.dataset.editable = "1";
				}
				);
		}
	}
	/*
	else{
		console.log("Edit mode is disabled");
	}*/
}

function populateDotArrayElement(element, dots_array, traitdata, current_val = false){
	var zdot_span = document.createElement('span');
	zdot_span.id = traitdata.trait+"-zerocontrol";
	zdot_span.dataset.traitid = traitdata.trait;
	zdot_span.dataset.dotbased = "1";
	zdot_span.dataset.dot_id = 0;
	if (current_val){
		zdot_span.dataset.current_val = "1";
		zdot_span.id = zdot_span.id+"-current";
	}
	zdot_span.innerHTML = window.dot_data.red_dot;
	if (window.charEditMode == false){
		zdot_span.style.display = "none";
	}
	if (!window.editElements.includes(zdot_span.id)){
		window.editElements.push(zdot_span.id);
	}
	element.appendChild(zdot_span);
	
	for (j = 0; j<dots_array.length; ++j) 
	{
		var dot_span = document.createElement('span');
		dot_span.dataset.traitid = traitdata.trait
		dot_span.dataset.dotbased = "1";
		dot_span.dataset.dot_id = j+1;
		if (current_val){
			dot_span.dataset.current_val = "1";
		}
		dot_span.innerHTML = dots_array[j];
		element.appendChild(dot_span);
	}
	return element;
}

function createMaxModElement(traitdata){
	var trait_maxmod = document.createElement('p');
	trait_maxmod.id = traitdata.trait+"-maxmod"
	if (window.charEditMode == false){
		trait_maxmod.style.display = "none";
	}	

	var desc = document.createElement('span');
	desc.innerHTML = getLangString("web_label_total")+": ";
	trait_maxmod.appendChild(desc);

	var val = document.createElement('span');
	val.innerHTML = traitdata.max_value
	val.dataset.traitid = traitdata.trait
	val.dataset.editable = "1"
	trait_maxmod.appendChild(val);

	if (!window.editElements.includes(trait_maxmod.id)){
		window.editElements.push(trait_maxmod.id)
	}		
	return trait_maxmod;
}

function createTraitElement(traitdata){
	var c = document.createElement('tr'); 
	c.setAttribute("id", traitdata.trait);

	var deletecontrol = document.createElement("span");
	deletecontrol.id = traitdata.trait+"-delet-control";
	deletecontrol.className = "material-icons md-18 delete_control";
	deletecontrol.innerHTML = "delete_forever";
	deletecontrol.dataset.traitid = traitdata.trait;
	deletecontrol.dataset.removetrait = "1"
	if (window.charEditMode == false){
		deletecontrol.style.display = "none";
	}	
	if (!window.editElements.includes(deletecontrol.id)){
		window.editElements.push(deletecontrol.id)
	}
	c.appendChild(deletecontrol);

	// tratti con visualizzazioni specifiche
	if (traitdata.trait == 'volonta')
	{
		var trait_title = document.createElement('h4');
		trait_title.innerHTML = getLangString("web_label_willpower")
		c.appendChild(trait_title);

		// permanent
		var dots_array = Array(traitdata.max_value).fill(window.dot_data.dot);
		var n_empty_dots = Math.max(0, 10-traitdata.max_value);
		if (n_empty_dots > 0)
			dots_array = dots_array.concat(Array(n_empty_dots).fill(window.dot_data.emptydot));
		
		var trait_dots = document.createElement('p');
		trait_dots = populateDotArrayElement(trait_dots, dots_array, traitdata);
		c.appendChild(trait_dots);

		// current
		var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
		var n_empty_dots = Math.max(0, 10-traitdata.cur_value);
		if (n_empty_dots > 0)
			sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
		
		var trait_sqrs = document.createElement('p');
		trait_dots = populateDotArrayElement(trait_sqrs, sqr_array, traitdata, true);
		c.appendChild(trait_sqrs);
	}
	else if (traitdata.trait == 'salute')
	{
		c.appendChild(createMaxModElement(traitdata));
		c.appendChild(renderhealth(traitdata['text_value'], traitdata['max_value']));
	}
	else if (traitdata.trait == 'exp') // i need this here because the other traits are in <td>'s -> might be worth to generalize
	{
		var trait_title = document.createElement('span');
		trait_title.innerHTML = out_sanitize(traitdata.traitName+': ');
		c.appendChild(trait_title);

		var trait_cont = document.createElement('span');
		trait_cont.id = traitdata.trait+'-content';
		trait_cont.innerHTML = traitdata.cur_value;
		trait_cont.dataset.traitid = traitdata.trait;
		trait_cont.dataset.editable = "1"
		trait_cont.dataset.current_val = "1"
		c.appendChild(trait_cont);		
	}
	else if (traitdata.traittype == 'uvp'){
		var trait_title = document.createElement('h4');
		trait_title.innerHTML = out_sanitize(traitdata.traitName)
		c.appendChild(trait_title);

		if (traitdata.trackertype == 0) // normale (umanità/vie)
		{
			var dots_array = Array(traitdata.max_value).fill(window.dot_data.dot);
			var n_empty_dots = Math.max(0, 10-traitdata.max_value);
			if (n_empty_dots > 0)
				dots_array = dots_array.concat(Array(n_empty_dots).fill(window.dot_data.emptydot));
			
			var trait_dots = document.createElement('p');
			trait_dots = populateDotArrayElement(trait_dots, dots_array, traitdata);
			c.appendChild(trait_dots);
		}
		else if (traitdata.trackertype == 1) // punti con massimo (sangue, yin...)
		{
			c.appendChild(createMaxModElement(traitdata));
			
			// current
			var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
			var n_empty_dots = Math.max(0, traitdata.max_value-traitdata.cur_value);
			if (n_empty_dots > 0)
				sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
			
			var trait_sqrs = document.createElement('p');
			trait_dots = populateDotArrayElement(trait_sqrs, sqr_array, traitdata, true);
			c.appendChild(trait_sqrs);

			
		}
		else if (traitdata.trackertype == 2) // danni (nessun uso al momento)
		{
			var trait_body = document.createElement('p');
			trait_body.innerHTML = out_sanitize(traitdata.text_value)+' (visualizzazione non implementata)'; //TODO
			c.appendChild(trait_body);
		}
		else if (traitdata.trackertype == 3) // punti senza massimo (nessun uso al momento)
		{
			var trait_body = document.createElement('p');
			trait_body.innerHTML = traitdata.cur_value;
			c.appendChild(trait_body);
		}
		else //fallback
		{
			var trait_body = document.createElement('p');
			trait_body.innerHTML = traitdata.cur_value + "/" + traitdata.max_value + " " +out_sanitize(traitdata.text_value)
			c.appendChild(trait_body);
		}
	}
	// tratti std
	else if (!traitdata.textbased)
	{
		var tname = out_sanitize(traitdata.traitName);
		if (!traitdata.standard && (['attitudine', 'capacita', 'conoscenza'].indexOf(traitdata.traittype) >= 0 ))
		{
			tname = '<b>'+tname+'</b>';
		}
		
		var trait_title = document.createElement('td');
		trait_title.className = "nopadding";
		trait_title.innerHTML = tname;
		c.appendChild(trait_title);
		
		if (traitdata.trackertype == 0) // normale
		{
			var dots_array = Array(Math.min(traitdata.cur_value,traitdata.max_value)).fill(window.dot_data.dot);
			if (traitdata.cur_value < traitdata.max_value)
				dots_array = dots_array.concat(Array(traitdata.max_value-traitdata.cur_value).fill(window.dot_data.red_dot));
			if (traitdata.cur_value>traitdata.max_value)
				dots_array = dots_array.concat(Array(traitdata.cur_value-traitdata.max_value).fill(window.dot_data.blue_dot));
			max_dots = Math.max(traitdata.pimp_max, 5)
			if (traitdata.cur_value < max_dots)
				dots_array = dots_array.concat(Array(max_dots-Math.max(traitdata.max_value, traitdata.cur_value)).fill(window.dot_data.emptydot));

			var trait_dots = document.createElement('td');
			trait_dots.className = "nopadding dotseq";
			trait_dots.style = "float:right";

			trait_dots = populateDotArrayElement(trait_dots, dots_array, traitdata);
			
			c.appendChild(trait_dots);
		}
		else if (traitdata.trackertype == 1) // punti con massimo (nessun uso al momento)
		{
			// current
			var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
			var n_empty_dots = Math.max(0, traitdata.max_value-traitdata.cur_value);
			if (n_empty_dots > 0)
				sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
			
			var trait_sqrs = document.createElement('td');
			trait_sqrs.className = "nopadding";
			trait_sqrs.style = "float:right";
			trait_dots = populateDotArrayElement(trait_sqrs, sqr_array, traitdata, true);
			c.appendChild(trait_sqrs);
			
			c.appendChild(createMaxModElement(traitdata));
		}
		else if (traitdata.trackertype == 2) // danni (nessun uso al momento)
		{
			var trait_body = document.createElement('td');
			trait_body.innerHTML = out_sanitize(traitdata.text_value)+' (visualizzazione non implementata)'; //TODO
			trait_body.className = "nopadding";
			trait_body.style = "float:right";
			c.appendChild(trait_body);
		}
		else if (traitdata.trackertype == 3) // punti senza massimo (nessun uso al momento)
		{
			var trait_body = document.createElement('p');
			trait_body.innerHTML = traitdata.cur_value;
			trait_body.className = "nopadding";
			trait_body.style = "float:right";
			c.appendChild(trait_body);
		}
		else //fallback
		{
			var trait_body = document.createElement('p');
			trait_body.innerHTML = traitdata.cur_value + "/" + traitdata.max_value + " " +out_sanitize(traitdata.text_value)
			trait_body.className = "nopadding";
			trait_body.style = "float:right";
			c.appendChild(trait_body);
		}
	}
	else // text based
	{
		var trait_title = document.createElement('span');
		trait_title.innerHTML = out_sanitize(traitdata.traitName);
		c.appendChild(trait_title);

		var ddot = document.createElement('span');
		ddot.id = traitdata.trait+"-separator";		
		ddot.innerHTML = ":&nbsp;";
		c.appendChild(ddot);

		var trait_text = document.createElement('span');
		trait_text.id = traitdata.trait + "-content";
		
		trait_text.innerHTML = out_sanitize(traitdata.text_value);
		trait_text.dataset.traitid = traitdata.trait;
		trait_text.dataset.textbased = "1";
		trait_text.dataset.editable = "1"
		c.appendChild(trait_text);

		if (traitdata.text_value === "-" || traitdata.text_value === "")
		{
			if (!window.charEditMode){
				trait_text.style.display = "none";
				ddot.style.display = "none";
			}
			if (! window.editElements.includes(trait_text.id))
			{
				window.editElements.push(trait_text.id);
			}
			if (! window.editElements.includes(ddot.id))
			{
				window.editElements.push(ddot.id);
			}
			if (traitdata.text_value === ""){
				trait_text.className = "empty_space_tofill";
			}
		}
		
		if (traitdata.trait == 'clan')
		{
			populate_clan_img(traitdata.text_value);
		}
	}
	return c;
}


function populateSheet(characterTraits, character){
	window.editElements = Array();
	disableCharEditMode(); // doing this here makes it faster because we don't have many items to disable
	// create new sheet
	var charsheet = window.sheet_template.cloneNode(true);
	charsheet.id ='charsheet';
	// insert new sheet
	var main = document.getElementById('main_content');
	main.appendChild(charsheet);

	//enable controls
	document.getElementById("newchar").style.display = 'block';

	const params = new URLSearchParams({
		charId: character.id
	});
	get_remote_resource('./canEditCharacter?'+params.toString(), 'json', 
					function (data){
						//console.log(data);
						var editcontrol = document.getElementById("editchar");
						var addtraitcharcontrol = document.getElementById("addtraitchar");
						if (data == 1){
							editcontrol.style.display = 'block';
							addtraitcharcontrol.style.display = 'block';
						}
						else{
							editcontrol.style.display = 'none';
							addtraitcharcontrol.style.display = 'none';
						}
					}/*, 
					function(xhr){
					}*/)

	// do stuff
	document.getElementById('title_pgname').innerHTML = '<b>'+character.fullname+'</b>';
	
	// nome del giocatore
	sheetspot = document.getElementById("testata");
	var c = document.createElement('tr'); 
	c.id = 'nome_giocatore';
	c.innerHTML = String.format(getLangString("web_string_charplayer"), character.ownername); 
	sheetspot.appendChild(c);
	
	var temp_dump = document.getElementById('altro');
	temp_dump.style.display = "none";
	/*var dot = "&#9899;"; //"⚫"; //9899
	var emptydot = "&#9898;"; //"⚪"; //9898
	var red_dot = "&#128308;";
	var blue_dot = "&#128309;";
	var square_full = "&#11035;"
	var square_empty = "&#11036;"*/
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
			var c = createTraitElement(traitdata);
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
			c.innerHTML = out_sanitize(traitdata.traitName) + ": " + traitdata.cur_value + "/" + traitdata.max_value + " " +out_sanitize(traitdata.text_value);
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
	// spegni blocchi vantaggi vuoti
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

	if (charsheet.addEventListener) {
		charsheet.addEventListener('click', editTrait, false);
	}
	else if (charsheet.attachEvent) {
		charsheet.attachEvent('onclick', function(e) {
			return editTrait.call(charsheet, e || window.event);
		});
	}

	window.selected_charid = character.id;
	var modregisterbtn = document.getElementById('modregister');
	modregisterbtn.style.display = "block";
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
	var side_menu_id = 'side_menu'
	var side_menu = document.getElementById(side_menu_id);

	// enable controls
	document.getElementById("newchar").style.display = 'block';

	// characters
	if (chars.length)
	{
		var title = document.createElement('h3');
		title.innerHTML = getLangString("web_label_chronicles")+":";
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
		c.id = character.id;
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

function default_error_callback(xhr){
	//callback(status, xhr.response);
	console.log('Error ('+xhr.status+') while getting remote resource '+xhr.url);
	post_error(xhr.status+": "+xhr.response);
}

function get_remote_resource(url, res_type, callback, error_callback = default_error_callback){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = res_type;
    xhr.onload = function() {
      var status = xhr.status;
      if (status === 200) {
        callback(xhr.response);
      } else {
        error_callback(xhr);
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

// ---

function translationSaved(data, id){
	var td = document.getElementById(id);
	td.innerHTML = out_sanitize(data.value, replace_HTMLElement);
	td.dataset.editable = "1";
}

function saveTranslation(id){
	var td = document.getElementById(id);
	input_id = td.id+'-input'
	var input_tag = document.getElementById(input_id);

	// todo post
	const params = new URLSearchParams({
		traitId: td.dataset.traitid,
		type: td.dataset.type,
		langId: td.dataset.langid,
		value: input_tag.value
	  });
	get_remote_resource('./editTranslation?'+params.toString(), 'json', function (data){
		translationSaved(data, id);
	})
}

function cancelTranslation(id){
	var td = document.getElementById(id);
	td.innerHTML = td.dataset.backup;
	td.dataset.editable = "1";
}

function editBox(event, save_function, cancel_function) {
    var td = event.target;
	if (td.dataset.editable === "1")
	{
		delete td.dataset.editable; //td.dataset.editable = "0";
		text = td.innerHTML
		td.dataset.backup = text;
		var input_id = td.id+'-input';
		
		var eb = document.createElement("div");
		eb.setAttribute("class", "w3-bar");

		var inp = document.createElement("input");
		inp.id = input_id;
		inp.className = "w3-bar-item w3-border w3-border-gray";
		inp.setAttribute("value", text);
		eb.appendChild(inp);

		var btnSave = document.createElement("button");
		btnSave.className = "w3-bar-item w3-btn w3-green";
		btnSave.addEventListener('click', function(event){
			save_function(td.id);
		})
		btnSave.innerHTML = '<span class="material-icons md-18">save</span>';
		eb.appendChild(btnSave)

		var btnCancel = document.createElement("button");
		btnCancel.className = "w3-bar-item w3-btn w3-red";
		btnCancel.addEventListener('click', function(event){
			cancel_function(td.id);
		})
		btnCancel.innerHTML = '<span class="material-icons md-18">cancel</span>';
		eb.appendChild(btnCancel)

		td.innerHTML = '';
		td.appendChild(eb);

		var input = document.getElementById(input_id);
		input.addEventListener("keyup", function(event) {
			if (event.key === 'Enter') {
				save_function(td.id);
			}
		}); 
		input.focus();
	}
}

function editBoxTranslate(event){
	return editBox(event, saveTranslation, cancelTranslation);
}

function translationEdit_page(){
	var container = document.getElementById("main");
	if (container.addEventListener) {
		container.addEventListener('click', editBoxTranslate, false);
	}
	else if (container.attachEvent) {
		container.attachEvent('onclick', function(e) {
			return editBoxTranslate.call(container, e || window.event);
		});
	}
	get_remote_resource('./getLanguageDictionary', 'json', function (dictionary){
		window.language_dictionary = dictionary;
	})
}

function autocomplete(inp, arr) {
	/*the autocomplete function takes two arguments,
	the text field element and an array of possible autocompleted values:*/
	var currentFocus;
	/*execute a function when someone writes in the text field:*/
	inp.addEventListener("input", function(e) {
		var a, b, i, val = this.value;
		/*close any already open lists of autocompleted values*/
		closeAllLists();
		if (!val) { return false;}
		currentFocus = -1;
		/*create a DIV element that will contain the items (values):*/
		a = document.createElement("DIV");
		a.setAttribute("id", this.id + "autocomplete-list");
		a.setAttribute("class", "autocomplete-items");
		/*append the DIV element as a child of the autocomplete container:*/
		this.parentNode.appendChild(a);
		/*for each item in the array...*/
		for (i = 0; i < arr.length; i++) {
		  /*check if the item starts with the same letters as the text field value:*/
		  if (arr[i].display.substr(0, val.length).toUpperCase() == val.toUpperCase()) {
			/*create a DIV element for each matching element:*/
			b = document.createElement("DIV");
			/*make the matching letters bold:*/
			b.innerHTML = "<strong>" + arr[i].display.substr(0, val.length) + "</strong>";
			b.innerHTML += arr[i].display.substr(val.length);
			/*insert a input field that will hold the current array item's value:*/
			b.innerHTML += "<input type='hidden' value='" + arr[i].value + "'>";
			/*execute a function when someone clicks on the item value (DIV element):*/
				b.addEventListener("click", function(e) {
				/*insert the value for the autocomplete text field:*/
				inp.value = this.getElementsByTagName("input")[0].value;
				/*close the list of autocompleted values,
				(or any other open lists of autocompleted values:*/
				closeAllLists();
			});
			a.appendChild(b);
		  }
		}
	});
	/*execute a function presses a key on the keyboard:*/
	inp.addEventListener("keydown", function(e) {
		var x = document.getElementById(this.id + "autocomplete-list");
		if (x) x = x.getElementsByTagName("div");
		if (e.keyCode == 40) {
		  /*If the arrow DOWN key is pressed,
		  increase the currentFocus variable:*/
		  currentFocus++;
		  /*and and make the current item more visible:*/
		  addActive(x);
		} else if (e.keyCode == 38) { //up
		  /*If the arrow UP key is pressed,
		  decrease the currentFocus variable:*/
		  currentFocus--;
		  /*and and make the current item more visible:*/
		  addActive(x);
		} else if (e.keyCode == 13) {
		  /*If the ENTER key is pressed, prevent the form from being submitted,*/
		  e.preventDefault();
		  if (currentFocus > -1) {
			/*and simulate a click on the "active" item:*/
			if (x) x[currentFocus].click();
		  }
		}
	});
	function addActive(x) {
	  /*a function to classify an item as "active":*/
	  if (!x) return false;
	  /*start by removing the "active" class on all items:*/
	  removeActive(x);
	  if (currentFocus >= x.length) currentFocus = 0;
	  if (currentFocus < 0) currentFocus = (x.length - 1);
	  /*add class "autocomplete-active":*/
	  x[currentFocus].classList.add("autocomplete-active");
	}
	function removeActive(x) {
	  /*a function to remove the "active" class from all autocomplete items:*/
	  for (var i = 0; i < x.length; i++) {
		x[i].classList.remove("autocomplete-active");
	  }
	}
	function closeAllLists(elmnt) {
	  /*close all autocomplete lists in the document,
	  except the one passed as an argument:*/
	  var x = document.getElementsByClassName("autocomplete-items");
	  for (var i = 0; i < x.length; i++) {
		if (elmnt != x[i] && elmnt != inp) {
		x[i].parentNode.removeChild(x[i]);
	  }
	}
  }
  /*execute a function when someone clicks in the document:*/
  document.addEventListener("click", function (e) {
	  closeAllLists(e.target);
  });
  } 
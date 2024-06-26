window.WepAppState = null;

var _note_autosavetimer = 0;
var _chrload_loadtimeout = 0;

window.dot_data = {
	dot: "&#9899;", //"⚫"; //9899
	emptydot: "&#9898;", //"⚪"; //9898
	red_dot: "&#128308;",
	blue_dot: "&#128309;",
	square_full: "&#11035;",
	square_empty: "&#11036;",
};
var urlParams = new URLSearchParams(window.location.search);

var replace_HTMLElement = [];
replace_HTMLElement['&'] = '&amp;';
replace_HTMLElement['<'] = '&lt;';
replace_HTMLElement['>'] = '&gt;';
replace_HTMLElement['"'] = '&quot;';
replace_HTMLElement["'"] = '&#x27;';

PLAYER_EDIT_CONTROL = 'player-edit-control';
PLAYER_NAME_CONTROL = 'PLAYER_NAME_CONTROL';
CALCULATED_GEN_CONTROL = 'generazione_calcolata';

CHARACTER_ID_CONTROL = 'CHARACTER_ID_CONTROL';

TAB_MACROS = "tab_macros";

//var replace_HTMLattribute = []
//replace_HTMLattribute

class TabManager{
	constructor(tab_id, menu_id){
		this.tab_id = tab_id;
		this.menu_id = menu_id;
	}
	switch(){
		throw "Implement me!";
	}
	runswitch()
	{
		state = getState();
		try{
			// perform exit logic for prev tab
			state.tabs[state.current_tab].tabPost(this.tab_id);

			// run pre
			this.tabPre();

			//attempt switch
			this.switch();

			// hide current tab if different
			if (state.current_tab != this.tab_id)
			{
				var old = document.getElementById(state.current_tab);
				if (old !== null) // can happen
				{
					old.style.display = 'none';
				}
			}

			// set current tab
			state.current_tab = this.tab_id;
		}
		catch(err)
		{
			post_error(err);
		}
	}
	tabPost(new_tab_id){
		getState().runTabAvailability(new_tab_id);
	}
	tabPre(){
		//  hide own menu item
		this.hideTab();
	}
	isTabAvailable(new_tab_id)
	{
		return new_tab_id !== this.tab_id;
	}
	hideTab()
	{
		var mi = document.getElementById(this.menu_id);
		if (mi !== null){
			mi.style.display = 'none';
		}
	}
	showTab()
	{
		var mi = document.getElementById(this.menu_id);
		if (mi !== null){
			mi.style.display = 'block';
		}
	}
}

class TabMsg extends TabManager
{
	switch() {
		document.getElementById(this.tab_id).style.display = 'block';
	}
}
class TabCharSheet extends TabManager
{
	switch() {
		state = getState();
		if (state.selected_character === null){
			throw "No character selected!";
		}
		load_charSheet(state.selected_character);
	}
	tabPost(){
		super.tabPost();
		disableCharEditMode();
		// hide edit controls
		document.getElementById("editchar").style.display = 'none';	
		document.getElementById("addtraitchar").style.display = 'none';
	}
}
class TabCharNotes extends TabManager
{
	switch() {
		load_charNotes();
	}
	tabPost(){
		super.tabPost();
		save_note(false);
		getState().selected_noteid = null;
	}
}

class TabMacros extends TabManager
{
	switch() {
		load_Macros(state.selected_character);
	}
	tabPost(){
		super.tabPost();
		getState().selected_macro = null;
	}
}

function tabswitch(tab_id){
	var state = getState();

	//note: we currently reload the tab by design even if it's the same because the target char changes

	if (state.tabs[tab_id] === undefined)
	{
		post_error(getLangStringFormatted("web_error_invalid_tab", tab_id));
		return;
	}
	state.tabs[tab_id].runswitch();
}

class AppState {
	constructor() {
		this.tabs = [];
		this.tabs["central_msg"] = new TabMsg("central_msg");
		this.tabs["charsheet"] = new TabCharSheet("charsheet", "chartab");
		//this.tabs["translations"] = TODO;
		this.tabs["character_notes"] = new TabCharNotes("character_notes", "charnotes");
		this.tabs[TAB_MACROS] = new TabMacros(TAB_MACROS, "mi_macros");
		this.current_tab = "central_msg";

		this.loading_state = false;

		this.charEditMode = false;
		this.editElements = Array();
		this.traitList = null;
		this.userList = null;
		this.input_modal = null;
		this.noyes_modal = null;
		this.newchar_modal = null;
		this.message_modal = null;
		this.funcVisibility = null;

		this.sheet_template = null;
		this.selected_charid = null;
		this.selected_character = null;
		this.selected_noteid = null;
		this.language_dictionary = null;
		this.selected_macro = null;

		this.webAppSettings = null;
	}
	runTabAvailability(new_tab_id)
	{
		for (var key in this.tabs) {
			var tab =  this.tabs[key];
			if (tab.isTabAvailable(new_tab_id))
			{
				tab.showTab();
			}else
			{
				tab.hideTab();
			}
		}
	}
}

function getState(){
	if (window.WepAppState === null)
	{
		window.WepAppState = new AppState();
	}
	return window.WepAppState;
}

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


function getLangStringFormatted(string_id){
	var args = Array.prototype.slice.call(arguments, 1);
	return String.format(getLangString(string_id), ...args);
}

function getLangString(string_id){
	// output sanitization is a bit overkill here
	state = getState();
	if (state.language_dictionary && state.language_dictionary[string_id]){
		return out_sanitize(state.language_dictionary[string_id], replace_HTMLElement)
	}
	else
	{
		console.log("could not load string:", string_id);
		return out_sanitize(string_id, replace_HTMLElement);
	}
}


// input modal

/**
 * 
 * @param {string} modal_title 
 * @param {string} placeholder_text 
 * @param {callback} onsave_func 
 * @param {*} autocomplete_data 
 * @param {string} ok_btn_text 
 */
 function flow_input_modal(modal_title, placeholder_text, onsave_func, autocomplete_data = null, ok_btn_text = "web_label_save")
 {
	 if (getState().input_modal != null){
		 // inject the modal
		 var modal_area = document.getElementById('inputmodal_area');	
		 modal_area.innerHTML = getState().input_modal
 
		 var modal = document.getElementById('input_modal')
		 modal.style.display = 'block';
		 // setup the modal
		 document.getElementById('input_modal_title').innerHTML = getLangString(modal_title);
		 var form = document.getElementById('input_modal_form');
 
		 var input_tag = document.getElementById('input_modal_myInput');
		 input_tag.setAttribute("placeholder", getLangString(placeholder_text)+"...");
 
		 var input_save = document.getElementById('input_modal_submit');
		 input_save.innerHTML = getLangString(ok_btn_text);
		 input_save.addEventListener('click', function(event){
			 var inp = document.getElementById('input_modal_myInput');
			 
			 onsave_func(inp.value);
 
			 modal.style.display='none';
			 modal.remove();
		 });
 
		 if (autocomplete_data !== null)
		 {
			 autocomplete(document.getElementById("input_modal_myInput"), autocomplete_data);
		 }
	 }
	 else{
		 console.log("not yet!");
	 }
 }
 


function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function getMyCharacters(dictionary){
	getState().language_dictionary = dictionary;
    get_remote_resource('./getMyCharacters', 'json',  getCharMenuItem, error_callback_onlyconsolelog);
}

function openNewChar(event){
	state = getState();
	if (state.newchar_modal){
		// inject the modal
		var modal_area = document.getElementById('newchar_modal_area');	
		modal_area.innerHTML = state.newchar_modal

		var modal = document.getElementById('new_char_modal')
		modal.style.display = 'block';

		// setup the modal
		var submit = document.getElementById('newchar_modal_submit');
		submit.addEventListener('click', function (event){
			var charId = document.getElementById('newchar_modal_charId').value;
			var charName = document.getElementById('newchar_modal_charName').value;
			const params = new URLSearchParams({
				charId: charId,
				charName: charName
			});
			get_remote_resource('./newCharacter?'+params.toString(), 'json',  function(data){
				const params = new URLSearchParams({
					character: data.charId
				});
				window.location.href = './?'+params.toString();
			});
		});
	}
	else{
		console.log("newchar modal not loaded!")
	}
}

function openNewTrait(){
	flow_input_modal("web_label_add_trait", "web_label_trait", function(inp) {
		// todo post
		const params = new URLSearchParams({
			traitId: inp,
			charId: getState().selected_charid
		});
		get_remote_resource('./editCharacterTraitAdd?'+params.toString(), 'json', 
		function (traitdata){
			var sheetspot = document.getElementById(traitdata.traittype);
			if (sheetspot)
			{
				var c = createTraitElement(traitdata);
				sheetspot.appendChild(c);

				var generation = getGeneration(traitdata);
				if (generation>=0)
				{
					renderCalcGeneration(generation);
				}
			}
		})
	}, getState().traitList);
}

function openChangePlayer(){
	flow_input_modal("web_label_change_player", "web_label_user", function(inp){
		// todo post
		const params = new URLSearchParams({
			userId: inp,
			charId: getState().selected_charid
		});
		get_remote_resource('./editCharacterReassign?'+params.toString(), 'json', 
		function (data){
			var newPlayer = createPlayerNameControl(data.name);
			var oldPlayer = document.getElementById(PLAYER_NAME_CONTROL);
			oldPlayer.parentNode.replaceChild(newPlayer, oldPlayer);
			// TODO should unload the character if we lost access to it, and also reload the character list
		})
	}, getState().userList);
}

function enableCharEditMode(){
	state = getState();
	if (state.traitList == null){
		get_remote_resource('./traitList', 'json', function(data){state.traitList = data});
	}	
	if (state.userList == null){
		get_remote_resource('./userList', 'json', function(data){state.userList = data});
	}

	var editcontrol = document.getElementById("editchar");
	editcontrol.innerHTML = getLangString("web_label_fihishedit_character");
	var addtraitcharcontrol = document.getElementById("addtraitchar");
	addtraitcharcontrol.style.display = 'block';

	state.charEditMode = true;
	for (i = 0; i<state.editElements.length; ++i)
	{
		el = document.getElementById(state.editElements[i]);
		if (el !== null){ // some traits might have been removed from the character
			el.style.display = 'inline';
		}
	}
}

function disableCharEditMode(){
	state = getState();
	var editcontrol = document.getElementById("editchar");
	editcontrol.innerHTML = getLangString("web_label_edit_character");
	var addtraitcharcontrol = document.getElementById("addtraitchar");
	addtraitcharcontrol.style.display = 'none';

	state.charEditMode = false;
	for (i = 0; i<state.editElements.length; ++i)
	{
		el = document.getElementById(state.editElements[i]);
		if (el !== null){ // some traits might have been removed from the character
			el.style.display = 'none';
		}
	}
}

function switchEditMode(){
	if (getState().charEditMode){
		disableCharEditMode();
	}
	else{
		enableCharEditMode()
	}
}

function renderhealth(health_text, max_value, cur_value)
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
	health_render.setAttribute("class", 'w3-table'); // why charsheet?
	
	var hs = health_text;
    hs = hs + (" ".repeat(Math.max(cur_value-hs.length, 0)));
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
			if (j >= max_value)
				img.className = img.className + ' extra-health'
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

function rerenderTrait(data){
	var newTrait = createTraitElement(data);
	var oldTrait = document.getElementById(data.trait);
	oldTrait.parentNode.replaceChild(newTrait, oldTrait);

	var generation = getGeneration(data);
	if (generation>=0)
	{
		renderCalcGeneration(generation);
	}
}

function editTrait(event) {
    var span = event.target;
	//console.log(span);
	if (getState().charEditMode)
	{
		if (span.dataset.traitid)
		{
			if (span.dataset.removetrait){
				// todo post
				const params = new URLSearchParams({
					traitId: span.dataset.traitid,
					charId: getState().selected_charid
				});
				get_remote_resource('./editCharacterTraitRemove?'+params.toString(), 'json', 
				function (data){
					var oldTrait = document.getElementById(data.trait);
					//editElements = getState().editElements;
					//TODO: remove from ediTelements. nothing will break if we don't but it's less messy if we do
					oldTrait.remove();

					// remove calculated generation
					// this is bad because it is not aware if one of the other 3 is available, we need an internal model of the character with all the trait data. this will suffice for now
					if (data.trait ===  'generazione' || data.trait ===  '14gen' || data.trait === '15gen')
					{
						var old_gen = document.getElementById(CALCULATED_GEN_CONTROL);

						if (old_gen)
						{
							old_gen.remove();
						}
					}

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
							charId: getState().selected_charid,
							newValue: span.dataset.dot_id
						});
						get_remote_resource('./editCharacterTraitNumberCurrent?'+params.toString(), 'json', rerenderTrait/*, 
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
									charId: getState().selected_charid,
									newValue: input_tag.value
								});
								get_remote_resource('./editCharacterTraitNumberCurrent?'+params.toString(), 'json', rerenderTrait/*, 
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
							charId: getState().selected_charid,
							newValue: span.dataset.dot_id
						});
						get_remote_resource('./editCharacterTraitNumber?'+params.toString(), 'json', rerenderTrait/*, 
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
									charId: getState().selected_charid,
									newValue: input_tag.value
								});
								get_remote_resource('./editCharacterTraitNumber?'+params.toString(), 'json', rerenderTrait/*, 
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
							charId: getState().selected_charid,
							newValue: input_tag.value
						});
						get_remote_resource('./editCharacterTraitText?'+params.toString(), 'json', rerenderTrait/*, 
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
		else if (span.id === PLAYER_EDIT_CONTROL)
		{
			openChangePlayer();
		}
	}
}

function populateDotArrayElement(element, dots_array, traitdata, current_val = false, newline_after = 0){
	if (newline_after == 0)
	{
		newline_after = dots_array.length;
	}
	var current_line = document.createElement('div');

	var zdot_span = document.createElement('span');
	zdot_span.id = traitdata.trait+"-zerocontrol";
	zdot_span.title = '0';
	zdot_span.dataset.traitid = traitdata.trait;
	zdot_span.dataset.dotbased = "1";
	zdot_span.dataset.dot_id = 0;
	if (current_val){
		zdot_span.dataset.current_val = "1";
		zdot_span.id = zdot_span.id+"-current";
	}
	zdot_span.innerHTML = window.dot_data.red_dot;
	if (getState().charEditMode == false){
		zdot_span.style.display = "none";
	}
	if (!getState().editElements.includes(zdot_span.id)){
		getState().editElements.push(zdot_span.id);
	}
	current_line.appendChild(zdot_span);
	
	for (j = 0; j<dots_array.length; ++j) 
	{
		if ((j > 0) && (j % newline_after == 0)){
			element.appendChild(current_line);
			current_line = document.createElement('div');
		}
		var dot_span = document.createElement('span');
		dot_span.title = j+1;
		dot_span.dataset.traitid = traitdata.trait
		dot_span.dataset.dotbased = "1";
		dot_span.dataset.dot_id = j+1;
		if (current_val){
			dot_span.dataset.current_val = "1";
		}
		dot_span.innerHTML = dots_array[j];
		current_line.appendChild(dot_span);
	}
	element.appendChild(current_line);

	return element;
}

function createMaxModElement(traitdata){
	var trait_maxmod = document.createElement('p');
	trait_maxmod.id = traitdata.trait+"-maxmod"
	if (getState().charEditMode == false){
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

	if (!getState().editElements.includes(trait_maxmod.id)){
		getState().editElements.push(trait_maxmod.id)
	}		
	return trait_maxmod;
}

function traitElementValue_Failsafe(parent_node, traitdata)
{
	var trait_cur = document.createElement('span');
	trait_cur.innerHTML = traitdata.cur_value;
	trait_cur.dataset.traitid = traitdata.trait;
	trait_cur.dataset.editable = "1"
	trait_cur.dataset.current_val = "1"
	parent_node.appendChild(trait_cur);	

	var trait_sep = document.createElement('span');
	trait_sep.innerHTML = "/";
	parent_node.appendChild(trait_sep);	

	var trait_cont = document.createElement('span');
	trait_cont.id = traitdata.trait+'-content';
	trait_cont.innerHTML = traitdata.max_value;
	trait_cont.dataset.traitid = traitdata.trait;
	trait_cont.dataset.editable = "1"
	parent_node.appendChild(trait_cont);	
}

function createTraitElement(traitdata){
	state = getState();
	var c = document.createElement('tr'); 
	c.setAttribute("id", traitdata.trait);

	var deletecontrol = document.createElement("span");
	deletecontrol.id = traitdata.trait+"-delet-control";
	deletecontrol.title = 'delete trait';
	deletecontrol.className = "material-icons md-18 delete_control";
	deletecontrol.innerHTML = "delete_forever";
	deletecontrol.dataset.traitid = traitdata.trait;
	deletecontrol.dataset.removetrait = "1"
	if (state.charEditMode == false){
		deletecontrol.style.display = "none";
	}	
	if (!state.editElements.includes(deletecontrol.id)){
		state.editElements.push(deletecontrol.id)
	}
	c.appendChild(deletecontrol);

	var toomanydots = !traitdata.textbased && Math.max(traitdata.cur_value, traitdata.max_value)>state.webAppSettings.max_trait_output_size;

	// tratti con visualizzazioni specifiche
	if (traitdata.trait == 'volonta')
	{
		var trait_title = document.createElement('h4');
		trait_title.innerHTML = out_sanitize(traitdata.traitName);
		trait_title.title = traitdata.trait;
		c.appendChild(trait_title);

		if (toomanydots){
			traitElementValue_Failsafe(c, traitdata);
		}
		else {
			// permanent
			var dots_array = Array(traitdata.max_value).fill(window.dot_data.dot);
			var n_empty_dots = Math.max(0, 10-traitdata.max_value);
			if (n_empty_dots > 0)
				dots_array = dots_array.concat(Array(n_empty_dots).fill(window.dot_data.emptydot));
			
			var trait_dots = document.createElement('p');
			trait_dots = populateDotArrayElement(trait_dots, dots_array, traitdata, false, 10);
			c.appendChild(trait_dots);

			// current
			var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
			var n_empty_dots = Math.max(0, Math.max(traitdata.max_value, 10)-traitdata.cur_value);
			if (n_empty_dots > 0)
				sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
			
			var trait_sqrs = document.createElement('p');
			trait_dots = populateDotArrayElement(trait_sqrs, sqr_array, traitdata, true, 10);
			c.appendChild(trait_sqrs);
		}

	}
	else if (traitdata.trait == 'salute')
	{
		c.appendChild(createMaxModElement(traitdata));
		c.appendChild(renderhealth(traitdata['text_value'], traitdata['max_value'], traitdata['cur_value']));
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

		var trait_body = document.createElement('p');

		if (toomanydots){
			traitElementValue_Failsafe(trait_body, traitdata);
		}
		else {
			if (traitdata.trackertype == 0) // normale (umanità/vie)
			{
				var dots_array = Array(traitdata.max_value).fill(window.dot_data.dot);
				var n_empty_dots = Math.max(0, 10-traitdata.max_value);
				if (n_empty_dots > 0)
					dots_array = dots_array.concat(Array(n_empty_dots).fill(window.dot_data.emptydot));
				
				trait_body = populateDotArrayElement(trait_body, dots_array, traitdata, false, 10);
			}
			else if (traitdata.trackertype == 1) // punti con massimo (sangue, yin...)
			{
				c.appendChild(createMaxModElement(traitdata));
				
				// current
				var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
				var n_empty_dots = Math.max(0, traitdata.max_value-traitdata.cur_value);
				if (n_empty_dots > 0)
					sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
				
				trait_dots = populateDotArrayElement(trait_body, sqr_array, traitdata, true, 10);
			}
			else if (traitdata.trackertype == 2) // danni (nessun uso al momento)
			{
				trait_body.innerHTML = out_sanitize(traitdata.text_value)+' (visualizzazione non implementata)'; //TODO
			}
			else if (traitdata.trackertype == 3) // punti senza massimo (nessun uso al momento)
			{
				trait_body.innerHTML = traitdata.cur_value;
			}
			else //fallback
			{
				trait_body.innerHTML = traitdata.cur_value + "/" + traitdata.max_value + " " +out_sanitize(traitdata.text_value)
			}
		}
		
		c.appendChild(trait_body);
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
		trait_title.title = traitdata.trait;
		trait_title.innerHTML = tname;
		c.appendChild(trait_title);
		

		var trait_body = document.createElement('td');
		trait_body.className = "nopadding dotseq";
		trait_body.style = "float:right";

		if (toomanydots) {
			traitElementValue_Failsafe(trait_body, traitdata)
		}
		else
		{
			if (traitdata.trackertype == 0) // normale
			{
				var dots_array = Array(Math.min(traitdata.cur_value,traitdata.max_value)).fill(window.dot_data.dot);
				if (traitdata.cur_value < traitdata.max_value)
					dots_array = dots_array.concat(Array(traitdata.max_value-traitdata.cur_value).fill(window.dot_data.red_dot));
				if (traitdata.cur_value>traitdata.max_value)
					dots_array = dots_array.concat(Array(traitdata.cur_value-traitdata.max_value).fill(window.dot_data.blue_dot));
				max_dots = traitdata.dotvisualmax;
				if (traitdata.cur_value < max_dots)
					dots_array = dots_array.concat(Array(max_dots-Math.max(traitdata.max_value, traitdata.cur_value)).fill(window.dot_data.emptydot));

				trait_body = populateDotArrayElement(trait_body, dots_array, traitdata, false, 10);
			}
			else if (traitdata.trackertype == 1) // punti con massimo (nessun uso al momento)
			{
				// current
				var sqr_array = Array(traitdata.cur_value).fill(window.dot_data.square_full);
				var n_empty_dots = Math.max(0, traitdata.max_value-traitdata.cur_value);
				if (n_empty_dots > 0)
					sqr_array = sqr_array.concat(Array(n_empty_dots).fill(window.dot_data.square_empty));
				
				trait_body = populateDotArrayElement(trait_body, sqr_array, traitdata, true, 10);
				
				c.appendChild(createMaxModElement(traitdata));
			}
			else if (traitdata.trackertype == 2) // danni (nessun uso al momento)
			{
				trait_body.innerHTML = out_sanitize(traitdata.text_value)+' (visualizzazione non implementata)'; //TODO
			}
			else if (traitdata.trackertype == 3) // punti senza massimo (nessun uso al momento)
			{
				trait_body.innerHTML = traitdata.cur_value;
			}
			else //fallback
			{
				trait_body.innerHTML = traitdata.cur_value + "/" + traitdata.max_value + " " +out_sanitize(traitdata.text_value)
			}
		}
				
		c.appendChild(trait_body);
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
			if (!state.charEditMode){
				trait_text.style.display = "none";
				ddot.style.display = "none";
			}
			if (! state.editElements.includes(trait_text.id))
			{
				state.editElements.push(trait_text.id);
			}
			if (! state.editElements.includes(ddot.id))
			{
				state.editElements.push(ddot.id);
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

function createCharIdControl(charid)
{
	var c = document.createElement('tr'); 
	c.id = CHARACTER_ID_CONTROL;

	var char_id_span = document.createElement('span');
	char_id_span.id = 'id_personaggio';
	char_id_span.innerHTML = String.format(getLangString("web_string_charid"), charid); 
	c.appendChild(char_id_span);

	return c;
}

function createPlayerNameControl(ownername){
	var c = document.createElement('tr'); 
	c.id = PLAYER_NAME_CONTROL;

	var player_edit = document.createElement('span');
	player_edit.id = PLAYER_EDIT_CONTROL;
	player_edit.className = "material-icons md-18";
	player_edit.innerHTML = 'edit';
	if (!getState().charEditMode)
		player_edit.style.display = 'none';
	if (!getState().editElements.includes(player_edit.id)){
		getState().editElements.push(player_edit.id)
	}
	c.appendChild(player_edit);

	var player_name = document.createElement('span');
	player_name.id = 'nome_giocatore';
	player_name.innerHTML = String.format(getLangString("web_string_charplayer"), ownername); 
	c.appendChild(player_name);

	return c;
}

function getGeneration(traitdata)
{
	var generation = -1;

	if (traitdata.trait === 'generazione')
	{
		generation = 13-traitdata.cur_value;
	}
	if (traitdata.trait === '14gen')
	{
		generation = 14;
	}
	if (traitdata.trait === '15gen')
	{
		generation = 15;
	}

	return generation
}

function getGenerationalLimit(generation_number){
	if (generation_number >= 10) return '1';
	switch (generation_number){
		case 9:
			return '2';
		case 8:
			return '3';
		case 7:
			return '4';
		case 6:
			return '6';
		case 5:
			return '8';
		case 4:
			return '10';
		default:
			return '???'
	}
}

function renderCalcGeneration(generation)
{
	var sheetspot = document.getElementById("testata");
	if (sheetspot)
	{
		var c = document.createElement('tr'); 
		c.setAttribute("id", CALCULATED_GEN_CONTROL);
		c.innerHTML = String.format(getLangString("web_string_calc_generation"), generation) +', '+ String.format(getLangString("web_generational_blood_limit"), getGenerationalLimit(generation)).toLowerCase(); 
		
		var old_gen = document.getElementById(CALCULATED_GEN_CONTROL);

		if (old_gen)
		{
			old_gen.parentNode.replaceChild(c, old_gen)
		}
		else
		{
			sheetspot.appendChild(c);
		}
	}
}

function populateSheet(characterTraits, character){
	window.clearTimeout(_chrload_loadtimeout);
	state = getState();
	state.editElements = Array();
	disableCharEditMode(); // doing this here makes it faster because we don't have many items to disable
	// create new sheet
	var charsheet = state.sheet_template.cloneNode(true);
	charsheet.id ='charsheet';
	// insert new sheet
	var main = document.getElementById('main_content');
	main.appendChild(charsheet);

	//enable controls
	document.getElementById("action-menu").style.display = 'block'; // do i need this?
	document.getElementById("newchar").style.display = 'block';

	const params = new URLSearchParams({
		charId: character.id
	});
	get_remote_resource('./canEditCharacter?'+params.toString(), 'json', 
					function (data){
						//console.log(data);
						var editcontrol = document.getElementById("editchar");
						if (data == 1){
							editcontrol.style.display = 'block';
						}
						else{
							editcontrol.style.display = 'none';
						}
					}/*, 
					function(xhr){
					}*/)

	//notes
	//var notescontrol = document.getElementById("charnotes");
	//notescontrol.style.display = 'block';

	// do stuff
	document.getElementById('title_pgname').innerHTML = '<b>'+character.fullname+'</b>';
		
	sheetspot = document.getElementById("testata");

	//id del personaggio
	c = createCharIdControl(character.id)	
	sheetspot.appendChild(c);
	
	// nome del giocatore
	c = createPlayerNameControl(character.ownername)	
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
	// TODO: make it a flag somewhere
	var switchesVie = new Map([
	   ['viataum', true],
	   ['vianecro', true],
	   ['viaduranki', true],
	   ['viaahku', true],
	   ['viadarktaum', true],
	   ['brujerizmo', true],
	   ['viawanga', true]
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
			
			// adjust generation
			var temp_gen = getGeneration(traitdata);
			if (temp_gen >= 0)
			{
				generation = temp_gen;
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
	if (generation > 0)
	{
		renderCalcGeneration(generation);
	}
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

	state.selected_charid = character.id;
	state.selected_character = character;
	var modregisterbtn = document.getElementById('modregister');
	modregisterbtn.style.display = "block";
	var central_msg = document.getElementById('central_msg');
	central_msg.style.display = "none";
	charsheet.style.display = "inline";
	state.loading_state = false;
}

function load_charSheet(character){
	state = getState();
	if (state.loading_state)
	{
		post_error(getLangString("web_msg_charload_stillloading"));
		return
	}
	state.loading_state = true;
	_chrload_loadtimeout = window.setTimeout(function() {
		getState().loading_state = false
		post_message(getLangString("web_msg_charload_toolong"));
	}, 10000);

	var charsheet = document.getElementById('charsheet');
	if (charsheet)
	{
		charsheet.remove();
	}
	var central_msg = document.getElementById('central_msg');
	central_msg.innerHTML = '<i class="fa fa-refresh w3-spin"></i>';
	central_msg.style.display = "inline";
	get_remote_resource('./getCharacterTraits?charid='+character.id, 'json', function(data){populateSheet(data, character)});
}

function populate_charmenu(menuItem, chars){
	var loaded = urlParams.get('character') == null;
	var side_menu_id = 'side_menu'
	var side_menu = document.getElementById(side_menu_id);

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
		container_id = 'chronicle_container_'+character.chronicleid;
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
		c.addEventListener('click', function(chardata){
				var c = chardata; 
				return function() {
					//load_charSheet(c);
					getState().selected_character = c;
					tabswitch("charsheet");
				}
			}(character)
		)
		// load the character if needed:
		if (character.id === urlParams.get('character') && !loaded)
		{
			//load_charSheet(character);
			state.selected_character = character;
			tabswitch("charsheet");
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
	get_remote_resource('./getCharacterModLog?charid='+getState().selected_charid, 'text',  view_modlog);
}

function default_error_callback(xhr){
	//callback(status, xhr.response);
	console.log('Error ('+xhr.status+') while getting remote resource '+xhr.url);
	post_error(xhr.status+": "+xhr.response);
}

function error_callback_onlyconsolelog(xhr){
	console.log('Error ('+xhr.status+') while getting remote resource '+xhr.url);
}

function get_remote_resource(url, res_type, callback, error_callback = default_error_callback){
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = res_type;
    xhr.onload = function() {
		var status = xhr.status;
		if (status === 200) {
			callback(xhr.response);
		}
		else {
			error_callback(xhr);
		}
    };
    xhr.send();
}

function post_request(url, res_type, params, success_callback, error_callback = default_error_callback)
{
	var xhr = new XMLHttpRequest();
	xhr.open('POST', url, true);
    xhr.responseType = res_type;
	xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
	xhr.onload = function() {//Call a function when the state changes.
		var status = xhr.status;
		if (status === 200) {
			success_callback(xhr.response);
		} 
		else {
			error_callback(xhr);
		}
	}
	xhr.send(params);
}

function post_error(text){
    //updateStatus('Error!');

    //var main = document.getElementById('main');
    //var alertPanel = document.createElement('div');
    //alertPanel.innerHTML = '<div class="w3-panel w3-red">  <h3>Danger!</h3>  <p>'+text+'</p></div>';
    //main.appendChild(alertPanel);

	show_error_toast(text);

	//alert(text);
}


function post_message(text){
	show_msg_toast(text);
}

function populate_page(){
	state = getState();
	state.sheet_template = document.getElementById('charsheet_template');
	state.sheet_template.remove();
	var modlog = document.getElementById('modregister');
	modlog.addEventListener('click', load_modlog);
    //var side_menu = document.getElementById('side_menu');

	get_remote_resource('./webAppSettings', 'json', function(data){
		getState().webAppSettings = data;
	})

	get_remote_resource('./webFunctionVisibility', 'json', function(data){
		if (data.side_menu){
			document.getElementById("side_menu").style.display = 'block';
		}
		if (data.new_character){
			var el = document.getElementById("newchar")
			el.style.display = 'block';
			const params = new URLSearchParams({
				modalId: 'new_char_modal'
			});
			get_remote_resource('./getModal?'+params.toString(), 'html', function(data){
				getState().newchar_modal = data;
			}) 
			el.addEventListener('click', openNewChar);
		}
		if (data.translate_traits){
			document.getElementById("traittranslation").style.display = 'block';
		}
		getState().funcVisibility = data;
	})
	
	if (state.input_modal == null){
		get_remote_resource('../html_res/InputFieldModal.html', 'text',  function(modaldata){getState().input_modal = modaldata;});
	}
	if (state.noyes_modal == null){
		get_remote_resource('../html_res/noYesBox.html', 'text',  function(modaldata){getState().noyes_modal = modaldata;});
	}
	if (state.message_modal == null){
		get_remote_resource('../html_res/messageModal.html', 'text',  function(modaldata){getState().message_modal = modaldata;});
	}

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
		getState().language_dictionary = dictionary;
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

function ui_notes()
{
	if (getState().selected_character === null)
	{
		post_error(getLangString('string_error_no_character_loaded'));
	}
	else
	{
		tabswitch("character_notes");
	}
}

function load_charNotes()
{
	get_remote_resource('./characterNotesPage?charId='+getState().selected_charid, 'text',  view_notestab);
}

function load_note(noteid){
	save_note(true);
	state = getState();
	const params = new URLSearchParams({
		noteId: noteid,
		charId: state.selected_charid
	});
	get_remote_resource('./getCharacterNote?'+params.toString(), 'json', function(notedata){
		var textarea = document.getElementById("note_text");
		textarea.value = notedata.notetext;
		textarea.removeAttribute('disabled');
		state = getState();
		state.selected_noteid = notedata.noteid;
		document.getElementById("note_title").innerHTML = state.selected_character.fullname+": "+ notedata.noteid;
		//setup autosave
		textarea.addEventListener("keyup", function (event) {
			if (_note_autosavetimer){
				window.clearTimeout(_note_autosavetimer);
			}
			_note_autosavetimer = window.setTimeout(function() {
				save_note();
			}, 5000);
		})
	}) 
}

function save_note(silent=true){
	if (_note_autosavetimer){ // clear autosave timer so that we don't save if the user saves manually
		window.clearTimeout(_note_autosavetimer);
	}
	state = getState();
	note_text_node = document.getElementById("note_text");
	if (state.selected_noteid === null || note_text_node === null)
	{
		if (!silent) {
			post_error(getLangString("string_error_no_note_loaded"));
		}
		return;
	}
	const params = new URLSearchParams({
		noteId: state.selected_noteid,
		charId: state.selected_charid,
		noteText: note_text_node.value
	});

	post_request('./saveCharacterNote', 'json', params, function(silent_save)
	{
		return function(notedata){
			console.log("Note saved, updated rows:", notedata[0])
			if (!silent_save)
			{
				post_message(getLangString("string_msg_note_saved"));
			}
		}

	} (silent));
}

function new_note(){
	save_note(true);
	flow_input_modal("web_label_note_new", "web_label_note_name", function (inp) {
		const params = new URLSearchParams({
			noteId: inp,
			charId: getState().selected_charid
		});
		post_request('./newCharacterNote', 'json', params, 
		function (data){
			var menuDropDown = document.getElementById('note_list');
			createNoteItem(menuDropDown, data[0]);
			load_note(data[0]);
		})
	});

}

function delete_note(askconfirm)
{
	state = getState();
	if (state.selected_noteid === null)
	{
		post_error(getLangString("string_error_no_note_loaded"));
		return;
	}
	if (askconfirm)
	{
		noYesConfirm(
			getLangString("web_label_note_delet")+"?",
			function (){
				do_delete_note();
			},
			getLangString("web_label_ok"),
			getLangString("web_label_cancel")
		);
	}
	else
	{
		do_delete_note();
	}
}

function do_delete_note(){
	if (_note_autosavetimer){ // clear autosave timer
		window.clearTimeout(_note_autosavetimer);
	}
	state = getState();
	if (state.selected_noteid === null)
	{
		post_error(getLangString("string_error_no_note_loaded"));
		return;
	}
	const params = new URLSearchParams({
		noteId: state.selected_noteid,
		charId: state.selected_charid
	});

	post_request('./deleteCharacterNote', 'json', params, function(notedata){
		console.log("Note deleted, updated rows:", notedata[0]);
		post_message(getLangString("string_msg_note_deleted"));
		// cleanup
		getState().selected_noteid = null;
		document.getElementById("note_title").innerHTML = '';
		note_textarea = document.getElementById("note_text");
		note_textarea.value = '';
		note_textarea.setAttribute("disabled", 1);
		// reload notes
		get_remote_resource('./getCharacterNotesList?charId='+state.selected_charid, 'json',  setupNoteList);
	});
}

function createNoteItem(menu, noteid)
{
	var noteItem = document.createElement('a');
	noteItem.href = '#';
	noteItem.className = 'w3-bar-item w3-button';
	noteItem.innerText = noteid;
	noteItem.addEventListener("click", function (note_id) {
			return function(event)
			{
				load_note(note_id);
			}
		}(noteid)
	);
	menu.appendChild(noteItem);
}

function setupNoteList(notesList, load_noteid = null){
	var i;
	var menuDropDown = document.getElementById('note_list');
	while (menuDropDown.firstChild) { // clear garbage from note deletes
		menuDropDown.removeChild(menuDropDown.lastChild);
	}
	var load_id = 0;

	for (i = 0; i<notesList.length; ++i){
		createNoteItem(menuDropDown, notesList[i].noteid)
		if (notesList[i].noteid === load_noteid)
		{
			load_id = i;
		}
	}
	if (notesList.length){
		load_note(notesList[load_id].noteid)
	}

}

function view_notestab(content)
{
	state = getState();
	notes = document.getElementById("character_notes");
	if (notes === null)
	{
		notes = document.createElement('div');
		notes.id = "character_notes";
		notes.className = "w3-display-topmiddle under-navbar central_content tab-page"
		document.getElementById("main_content").appendChild(notes);
	}

	notes.innerHTML = content

	document.getElementById("note_save").addEventListener("click", function(event) {save_note(false);});
	document.getElementById("note_delete").addEventListener("click", function(event){delete_note(true);});
	document.getElementById("note_new").addEventListener("click", function(event) {new_note();}); 

	get_remote_resource('./getCharacterNotesList?charId='+state.selected_charid, 'json',  setupNoteList);

	notes.style.display = 'block';
}


// todo: 
function w3_open() {
	//document.getElementById("main_content").style.marginLeft = "25%";
	//document.getElementById("side_menu").style.width = "25%";
	document.getElementById("side_menu").style.display = "block";
	document.getElementById("openNav").style.display = 'none';
}
  
function w3_close() {
	document.getElementById("main_content").style.marginLeft = "0%";
	document.getElementById("side_menu").style.display = "none";
	document.getElementById("openNav").style.display = "inline-block";
}

//noyes

function noYesConfirm(title, yes_func, yes_text = "Y", no_text = "N", details="", no_func = function(){})
{
	state = getState();
	if (state.noyes_modal != null){
		// inject the modal
		var modal_area = document.getElementById('noyesbox_area');	
		modal_area.innerHTML = state.noyes_modal;
	
		var modal = document.getElementById('noyes_modal');
		modal.style.display = 'block';

		// setup the modal
		document.getElementById('noyes_modal_title').innerHTML = title;
	
		var yes_button = document.getElementById('input_modal_yes');
		yes_button.innerHTML = yes_text;
		yes_button.addEventListener('click', function(event){
			yes_func();
			modal.style.display='none';
			modal.remove();
		});

		var no_button = document.getElementById('input_modal_no');
		no_button.innerHTML = no_text;
		no_button.addEventListener('click', function(event){
			no_func();
			modal.style.display='none';
			modal.remove();
		});
	
	}
	else{
		console.log("not yet! executing yes_func directly!");
		yes_func(); // this is going to bite me in the ass lol
	}
}

// Macros

function load_Macros()
{
	get_remote_resource('./macrosPage?charId='+getState().selected_charid, 'text',  view_macrosTab);
}

function view_macrosTab(content) //copied from view_notes, the first bit is generalizable
{
	state = getState();
	macros = document.getElementById(TAB_MACROS);
	if (macros === null)
	{
		macros = document.createElement('div');
		macros.id = TAB_MACROS;
		macros.className = "w3-display-topmiddle under-navbar central_content tab-page"
		document.getElementById("main_content").appendChild(macros);
	}

	macros.innerHTML = content

	// setup buttons
	document.getElementById("macro_save").addEventListener("click", function(event) {save_macro(false);});
	document.getElementById("macro_delete").addEventListener("click", function(event) {delete_macro(true);});
	new_macro_btn = document.getElementById("macro_new_general");
	if (state.funcVisibility.macro_new_general)
	{
		new_macro_btn.addEventListener("click", function(event) {new_macro(null);}); 
		new_macro_btn.style.display = 'block';
	}
	else
	{
		new_macro_btn.style.display = 'none';
	}

	if (state.selected_character !== null)
	{
		document.getElementById("macro_new_char").addEventListener("click", function(event) {new_macro(state.selected_character.id);}); 
	}

	document.getElementById("macro_use").addEventListener("click", function(event) {use_macro(true);});

	reload_macros()
	
	macros.style.display = 'block';
}

function reload_macros()
{
	state = getState();

	// load general macros
	get_remote_resource('./getGeneralMacros', 'json', function (data) {setupMacroList('macros_general_container', data)});

	// load character macros
	if (state.selected_character !== null)
	{
		get_remote_resource('./getCharacterMacros?charId='+state.selected_charid, 'json', function (data) {setupMacroList('macros_character_container', data)});
	}
}

function setupMacroList(target_node, data)
{
	var i;
	var section_node = document.getElementById(target_node);
	var menu_node = document.getElementById(target_node+'_list');
	while (menu_node.firstChild) { // clear garbage from deletes
		menu_node.removeChild(menu_node.lastChild);
	}

	for (i = 0; i<data.length; ++i){
		createMacroItem(menu_node, data[i].macroid);
	}
	
	section_node.style.display = 'block';
}

function createMacroItem(menu, macro_id)
{
	var macroItem = document.createElement('a');
	macroItem.href = '#';
	macroItem.className = 'w3-button w3-bar-item';
	macroItem.innerText = macro_id;
	macroItem.addEventListener("click", function (macro_id) {
			return function(event)
			{
				load_macro(macro_id);
			}
		}(macro_id)
	);
	menu.appendChild(macroItem);
}

function load_macro(macro_id)
{
	//save_macro(true);
	state = getState();
	const params = new URLSearchParams({
		macroId: macro_id
	});
	get_remote_resource('./getMacro?'+params.toString(), 'json', function(macrodata){
		var textarea = document.getElementById("macro_text");
		textarea.value = macrodata.macrocommands;
		textarea.removeAttribute('disabled');
		state = getState();
		state.selected_macro = macrodata.macroid;
		title = macrodata.macroid
		if (state.selected_character !== null && macrodata.characterid !== null)
		{
			title = state.selected_character.fullname+": "+title
		}
		document.getElementById("macro_title").innerHTML = title;
		/*
		//setup autosave
		textarea.addEventListener("keyup", function (event) {
			if (_note_autosavetimer){
				window.clearTimeout(_note_autosavetimer);
			}
			_note_autosavetimer = window.setTimeout(function() {
				save_note();
			}, 5000);
		})*/
	}) 
}

function save_macro(silent = true)
{
	/*if (_note_autosavetimer){ // clear autosave timer so that we don't save if the user saves manually
		window.clearTimeout(_note_autosavetimer);
	}*/
	state = getState();
	macro_text_node = document.getElementById("macro_text");
	if (state.selected_macro === null || macro_text_node === null)
	{
		if (!silent) {
			post_error(getLangString("string_error_no_macro_loaded"));
		}
		return;
	}
	const params = new URLSearchParams({
		macroId: state.selected_macro,
		macroText: macro_text_node.value
	});

	post_request('./saveMacro', 'json', params, function(data){
		if (!silent)
		{
			post_message(getLangStringFormatted("web_msg_macro_saved", state.selected_macro) );
		}
	});
}
function new_macro(character_id)
{
	// save?
	flow_input_modal("web_label_macro_new", "web_label_macro_id", function(inp){
		var params = new URLSearchParams({
			macroId: inp,
		});
		var reqpage = './newGeneralMacro'
		var target_menu = 'macros_general_container_list'
		if (character_id !== null)
		{
			params.append('charId', character_id);
			reqpage = './newCharacterMacro'
			target_menu = 'macros_character_container_list'
		}

		post_request(reqpage, 'json', params, function (data){
			var menu = document.getElementById(target_menu);
			createMacroItem(menu, data[0]);
			load_macro(data[0]);
		}/*, 
		function(xhr){
		}*/)
	});
}

function delete_macro(askconfirm = true)
{
	state = getState();
	if (state.selected_macro === null)
	{
		post_error(getLangString("string_error_no_macro_loaded"));
		return;
	}
	if (askconfirm)
	{
		noYesConfirm(
			getLangString("web_label_macro_delet")+"?",
			function (){
				do_delete_macro();
			},
			getLangString("web_label_ok"),
			getLangString("web_label_cancel")
		);
	}
	else
	{
		do_delete_macro();
	}
}

function do_delete_macro()
{
	/*if (_note_autosavetimer){ // clear autosave timer
		window.clearTimeout(_note_autosavetimer);
	}*/
	state = getState();
	if (state.selected_macro === null)
	{
		post_error(getLangString("string_error_no_macro_loaded"));
		return;
	}
	const params = new URLSearchParams({
		macroId: state.selected_macro
	});

	post_request('./deleteMacro', 'json', params, function(data){
		post_message(getLangString("string_msg_macro_deleted"));
		// cleanup
		getState().selected_macro = null;
		document.getElementById("macro_title").innerHTML = '';
		textarea = document.getElementById("macro_text");
		textarea.value = '';
		textarea.setAttribute("disabled", 1);
		// reload macros
		reload_macros()
	});
}

function use_macro(askconfirm = true)
{
	state = getState();
	if (state.selected_macro === null)
	{
		post_error(getLangString("string_error_no_macro_loaded"));
		return;
	}
	if (askconfirm)
	{
		noYesConfirm(
			getLangString("web_label_macro_use")+"?",
			function (){
				do_use_macro();
			},
			getLangString("web_label_ok"),
			getLangString("web_label_cancel")
		);
	}
	else
	{
		do_use_macro();
	}
}

function do_use_macro()
{
	state = getState();
	if (state.selected_macro === null)
	{
		post_error(getLangString("string_error_no_macro_loaded"));
		return;
	}
	const params = new URLSearchParams({
		macroId: state.selected_macro,
		charId: state.selected_charid
	});

	post_request('./useMacro', 'json', params, function(data){
		modal = message_modal("web_label_macro_results");
		fillMacroResults(modal, data);
	});
}

class RollItemFormatter
{
	format(rollitem)
	{
		var s = 'Work in progress. '
		return s.concat(rollitem.tag, ' diff ', rollitem.difficulty, ': ', rollitem.results, ' successes: ', rollitem.count_successes);
	}
}

class RollDataFormatter
{
	output(rolldata){
		var formatterCls = this.getItemFormatter(rolldata);
		var formatter = new formatterCls();

		var element = document.createElement('div');

		for (var i = 0; i<rolldata.data.length; ++i){
			var itemElement =  document.createElement('p');
			var dataitem = rolldata.data[i];
			itemElement.innerHTML = formatter.format(dataitem);
			element.appendChild(itemElement);
		}

		return element;
	}
	getItemFormatter(rolldata){
		return RollItemFormatter
	}
}

function createRollDataElement(rolldata)
{
	var rf = new RollDataFormatter()

	return rf.output(rolldata);
}

function fillMacroResults(node, data)
{
	for (var i = 0; i<data.length; ++i){
		dataitem = data[i]
		var childItem;
		if (dataitem.type === 'TEXT'){
			childItem = document.createElement('p');
			childItem.innerHTML = out_sanitize(dataitem.data);
		}
		else if (dataitem.type === 'TRAIT') {
			childItem = createTraitElement(dataitem.data)
		}
		else if (dataitem.type === 'ROLL') {
			childItem = createRollDataElement(dataitem.data)
		}
		node.appendChild(childItem);
	}
}


//Message Modal

function message_modal(modal_title)
{
	state = getState();
	if (state.message_modal != null){
		// inject the modal
		var modal_area = document.getElementById('message_modal_area');	
		modal_area.innerHTML = state.message_modal

		var modal = document.getElementById('message_modal')
		modal.style.display = 'block';
		
		// setup the modal
		document.getElementById('message_modal_title').innerHTML = getLangString(modal_title);
		
		return document.getElementById('message_modal_details')
	}
	else{
		console.log("not yet!");
		return null;
	}
}

//error

function show_toast(message, toast_class, showtime = 3000){
	var x = document.getElementById("msg_toast");
	x.className = "show "+toast_class;
	x.innerHTML = message;
	setTimeout(function(){ x.className = x.className.replace("show", ""); }, showtime);
}

function show_error_toast(text = 'Error') {
	show_toast(text, "error_toast");
}

function show_msg_toast(text = 'Message') {
	show_toast(text, "msg_toast");
}


function getCharMenuItem(characters){
	get_remote_resource('../html_res/charMenuItem.html', 'text',  function(menuItem){populate_charmenu(menuItem, characters)});
}

function populateSheet(characterTraits){
	var main_sheet = document.getElementById('main_sheet');
	main_sheet.innerHTML = ''
	var i;
    for (i = 0; i<characterTraits.length; ++i){
		traitdata = characterTraits[i];
        var c = document.createElement('p');
        //c.innerHTML = menuItem;
		//c = c.firstChild
		c.setAttribute("id", traitdata.trait);
		c.innerHTML = traitdata.name + ": " + traitdata.cur_value + "/" + traitdata.max_value + " " +traitdata.text_value
        main_sheet.appendChild(c);
		//c.addEventListener('click', function(id){var cid = id; return function() {load_charSheet(cid);}}(character.id))
	}
}

function load_charSheet(charid){
	get_remote_resource('./getCharacterTraits?charid='+charid, 'json', populateSheet);
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
		c.addEventListener('click', function(id){var cid = id; return function() {load_charSheet(cid);}}(character.id))
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
    //var side_menu = document.getElementById('side_menu');
    get_remote_resource('./getMyCharacters', 'json',  getCharMenuItem);
}
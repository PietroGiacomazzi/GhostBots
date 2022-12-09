-- Macro Table

create table CharacterMacro(
	characterid nvarchar(20),
	macroid nvarchar(20) not null,
    macrocommands TEXT(65535) not null,
	primary key (macroid),
	foreign key (characterid) references PlayerCharacter(id)
		on delete cascade
		on update cascade
)Engine=InnoDB;

insert into CharacterMacro(characterid, macroid, macrocommands) values (NULL, "wake", "me sangue -1\nsilent_mode_on\nme salute -1c\nsilent_mode_off\nme salute -1c");
insert into CharacterMacro(characterid, macroid, macrocommands) values ("lilith", "wadjet", "me forza = 4\nme destrezza  = 3\nme costituzione = 2\nme percezione = 3\nme intelligenza = 3\nme prontezza = 3\nme carisma = 4\nme persuasione =  4\nme aspetto = 1"); 

-- health management update

update CharacterTrait set pimp_max = 100 where trait = 'salute'

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

insert into CharacterMacro(characterid, macroid, macrocommands) values (NULL, "wake", "me sangue -1\n#me danni -1c\nme danni -1c");
insert into CharacterMacro(characterid, macroid, macrocommands) values (NULL, "reset", "me forza reset\nme destrezza reset\nme costituzione reset\n\nme carisma reset\nme persuasione reset\nme aspetto reset\n\nme percezione reset\nme intelligenza reset\nme prontezza reset\n\nme salute reset");
insert into CharacterMacro(characterid, macroid, macrocommands) values ("lilith", "wadjet", "me forza = 4\nme destrezza  = 3\nme costituzione = 2\nme percezione = 3\nme intelligenza = 3\nme prontezza = 3\nme carisma = 4\nme persuasione =  4\nme aspetto = 1"); 

-- health management update

update CharacterTrait set pimp_max = 100 where trait = 'salute'

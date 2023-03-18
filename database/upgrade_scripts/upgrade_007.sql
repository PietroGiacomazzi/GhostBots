/* This stuff is just WIP */

create table TraitLink(
	gamesystemid nvarchar(20) not null,
	traitid nvarchar(20) not null,
	linkedtraitid nvarchar(20) not null,
	primary key (gamesystemid, traitid, linkedtraitid),
	foreign key (gamesystemid) references Gamesystem(gamesystemid)
		on delete cascade
		on update cascade,
	foreign key (traitid)  references Trait(id)
		on delete cascade
		on update cascade,
)Engine=InnoDB;

/* IDEA:
	Traits should just define the id, and everything else should be linked to a system

	- Make Trait Type be a system thing
		- Add gamesystemid to TraitType and in its PK
		- Create a MtM table between Trait and TraitType (that also includes the gamesystemid)
		- [MAINTAIN] create the correct records using the traittype field in Trait and fixing the GS (STS probably)
		- remove TraitType from Trait
	- Make a TraitDetail table that has system specific data for the trait:
		- PK: Traitid, gamesystemid
		- Standard
		- Ordering
		- TrackerType
	- [MAINTAIN] move current data over to new table wiwth STS GS
	- remove from trait:
		- Name
		- TraitType
		- TrackerType
		- Standard
		- Ordering

	at this point it's probaby just better to add the gamesystemid field to Trait and TraitType and in their PKs
	but i lose translations

	# DND proficiencies:
	we haave a proficiency trait that stores the prof bonus
	the skill trait will just contain the fact that a character is proficient:
		if char no  arcana trait: char cannot roll arcana
		if char has arcana with value 0: char is not proficient
		if char has arcana 1: char is proficient
		if char has arcana 2: char has exprt proficiency
	so basically: wew multiply the value of the skill trait with the value of the proficiency bonuys to get the skill modifier.

*/
insert into TraitType (id, name, sheetspot, textbased) values ('dnd5e', 'Dungeons and Dragons 5E', 'default', 0);

insert into Trait (id, name, traittype, trackertype, standard, ordering) values 
	('competenza', 'blah', 'dnd5e', 0, 0, 0),
	('saggezza', 'blah', 'dnd5e', 0, 0, 0),
	('arcana', 'blah', 'dnd5e', 0, 0, 0),
	('raggirare', 'blah', 'dnd5e', 0, 0, 0);

-- traitlang insert from select

insert into TraitLink (gamesystemid, traitid, linkedtraitid) values 
	('DND_5E', 'acrobazia', 'destrezza'),
	('DND_5E', 'animali', 'saggezza'),
	('DND_5E', 'arcana', 'intelligenza'),
	('DND_5E', 'atletica', 'forza'),
	('DND_5E', 'raggirare', 'carisma'),
	('DND_5E', 'storia', 'intelligenza'),
	('DND_5E', 'intuito', 'saggezza'),
	('DND_5E', 'intimidire', 'carisma'),
	('DND_5E', 'investigare', 'intelligenza'),
	('DND_5E', 'medicina', 'saggezza'),
	('DND_5E', 'natura', 'intelligenza')
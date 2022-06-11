create table BotGuild(
	guildid nvarchar(32) not null,
	guildname nvarchar(32) not null,
    authorized boolean not null,
	primary key (guildid)
)Engine=InnoDB;

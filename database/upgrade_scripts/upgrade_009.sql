ALTER TABLE GameSession ADD gamestateid SMALLINT NOT NULL DEFAULT 0;

-- dio stracane porco madonna puttana
CREATE TABLE TraitSettings (
    traitid varchar(20) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci not null, 
    gamestateid smallint not null,
    rollpermanent BOOLEAN not null DEFAULT 0,
    autopenalty BOOLEAN not null DEFAULT 0,
    primary key (traitid, gamestateid),
    foreign key (traitid) references Trait(id)
        on update cascade
        on delete cascade
)
    Engine=InnoDB 
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_general_ci
    ;

INSERT INTO TraitSettings (traitid, gamestateid, rollpermanent, autopenalty) VALUES
('forza',     1, 0, 1),
('destrezza', 1, 0, 1),
('volonta',   0, 1, 0);
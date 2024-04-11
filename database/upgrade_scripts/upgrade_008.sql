insert into ClanInfo (clanId, clanimgurl) values
('Gargoyle', 'LogoBloodlineGargoyles.webp');

ALTER TABLE TraitType ADD dotvisualmax SMALLINT DEFAULT 0;
ALTER TABLE CharacterTrait DROP COLUMN pimp_max;

update TraitType set dotvisualmax = 5;
update TraitType set dotvisualmax = 6 where id in ('fisico', 'mentale', 'sociale');
update TraitType set dotvisualmax = 10 where id in ('uvp');
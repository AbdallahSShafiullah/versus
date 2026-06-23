-- VERSUS skeleton schema
-- Run:  mysql -u root -p versus < schema.sql
--
-- The four core tables for Phase I.
-- Students will extend with: predictions, votes, achievements,
-- user_achievements, follows, comments, plus triggers and a stored procedure.

DROP DATABASE IF EXISTS versus;
CREATE DATABASE versus;
USE versus;

CREATE TABLE Users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password      VARCHAR(255) NOT NULL,
    bio           TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Brackets (
    bracket_id           INT AUTO_INCREMENT PRIMARY KEY,
    host_id              INT NOT NULL,
    title                VARCHAR(255) NOT NULL,
    description          TEXT,
    entrant_count        INT NOT NULL,
    status               ENUM(
                             'draft',
                             'predictions_open',
                             'round_1','round_2','round_3','round_4','round_5',
                             'completed'
                         ) NOT NULL DEFAULT 'predictions_open',
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_entrant_count CHECK (entrant_count IN (4,8,16,32)),
    CONSTRAINT fk_brackets_host  FOREIGN KEY (host_id) REFERENCES Users(user_id)
);

CREATE TABLE Entrants (
    entrant_id   INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id   INT NOT NULL,
    seed         INT NOT NULL,
    name         VARCHAR(255) NOT NULL,
    CONSTRAINT fk_entrants_bracket FOREIGN KEY (bracket_id) REFERENCES Brackets(bracket_id),
    CONSTRAINT uq_entrants_seed    UNIQUE (bracket_id, seed)
);

CREATE TABLE Matchups (
    matchup_id          INT AUTO_INCREMENT PRIMARY KEY,
    bracket_id          INT NOT NULL,
    round               INT NOT NULL,
    slot                INT NOT NULL,
    entrant_a_id        INT,
    entrant_b_id        INT,
    winner_entrant_id   INT,
    votes_a             INT NOT NULL DEFAULT 0,
    votes_b             INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_matchups_bracket FOREIGN KEY (bracket_id)        REFERENCES Brackets(bracket_id),
    CONSTRAINT fk_matchups_a       FOREIGN KEY (entrant_a_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_b       FOREIGN KEY (entrant_b_id)      REFERENCES Entrants(entrant_id),
    CONSTRAINT fk_matchups_winner  FOREIGN KEY (winner_entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_matchups_slot    UNIQUE (bracket_id, round, slot)
);

-- Adding this comment as sepeartion from my code and code that was in the skeleton 

CREATE TABLE Predictions (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT NOT NULL,
    matchup_id    INT NOT NULL,
    entrant_id    INT NOT NULL,
    is_correct    BOOLEAN DEFAULT NULL,
    points        INT DEFAULT 0,
    submitted_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pred_user    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_pred_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id),
    CONSTRAINT fk_pred_entrant FOREIGN KEY (entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_pred_user_matchup UNIQUE (user_id, matchup_id)
);

CREATE TABLE Votes (
    vote_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    matchup_id   INT NOT NULL,
    entrant_id   INT NOT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_vote_user    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_vote_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id),
    CONSTRAINT fk_vote_entrant FOREIGN KEY (entrant_id) REFERENCES Entrants(entrant_id),
    CONSTRAINT uq_vote_user_matchup UNIQUE (user_id, matchup_id)
);

CREATE TABLE Achievements (
    code        VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);

INSERT INTO Achievements (code, name, description) VALUES
('bracket_maker', 'Bracket Maker', 'Hosted your first bracket.'),
('locked_in', 'Locked In', 'Submitted your 10th prediction.');

CREATE TABLE User_Achievements (
    user_id     INT NOT NULL,
    code        VARCHAR(50) NOT NULL,
    earned_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, code),
    CONSTRAINT fk_ua_user FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_ua_code FOREIGN KEY (code) REFERENCES Achievements(code)
);

CREATE TABLE Follows (
    follower_id INT NOT NULL,
    followed_id INT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    CONSTRAINT fk_follows_follower FOREIGN KEY (follower_id) REFERENCES Users(user_id),
    CONSTRAINT fk_follows_followed FOREIGN KEY (followed_id) REFERENCES Users(user_id),
    CONSTRAINT chk_no_self_follow  CHECK (follower_id != followed_id)
);

CREATE TABLE Comments (
    comment_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    matchup_id  INT NOT NULL,
    body        TEXT NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comment_user FOREIGN KEY (user_id) REFERENCES Users(user_id),
    CONSTRAINT fk_comment_matchup FOREIGN KEY (matchup_id) REFERENCES Matchups(matchup_id)
);

CREATE INDEX idx_matchups_bracket_round ON Matchups(bracket_id, round);
CREATE INDEX idx_predictions_user ON Predictions(user_id);





-- TRIGGERS
DELIMITER //

-- BEFORE INSERT Predictions: Only allow if predictions_open
CREATE TRIGGER trg_check_predictions_open
BEFORE INSERT ON Predictions
FOR EACH ROW
BEGIN
    DECLARE b_status VARCHAR(50);
    SELECT b.status INTO b_status
    FROM Brackets b
    JOIN Matchups m ON b.bracket_id = m.bracket_id
    WHERE m.matchup_id = NEW.matchup_id;

    IF b_status != 'predictions_open' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Predictions are closed for this bracket.';
    END IF;
END //

-- BEFORE INSERT Votes: Only allow if bracket status matches matchup round
CREATE TRIGGER trg_check_votes_round
BEFORE INSERT ON Votes
FOR EACH ROW
BEGIN
    DECLARE b_status VARCHAR(50);
    DECLARE m_round INT;
    DECLARE expected_status VARCHAR(50);

    SELECT b.status, m.round INTO b_status, m_round
    FROM Brackets b
    JOIN Matchups m ON b.bracket_id = m.bracket_id
    WHERE m.matchup_id = NEW.matchup_id;

    SET expected_status = CONCAT('round_', m_round);

    IF b_status != expected_status THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Voting is not open for this round.';
    END IF;
END //

-- AFTER INSERT Brackets: Award 'bracket_maker' achievement
CREATE TRIGGER trg_award_bracket_maker
AFTER INSERT ON Brackets
FOR EACH ROW
BEGIN
    DECLARE host_count INT;
    SELECT COUNT(*) INTO host_count FROM Brackets WHERE host_id = NEW.host_id;
    IF host_count = 1 THEN
        INSERT IGNORE INTO User_Achievements (user_id, code) VALUES (NEW.host_id, 'bracket_maker');
    END IF;
END //

-- AFTER INSERT Predictions: Award 'locked_in' achievement
CREATE TRIGGER trg_award_locked_in
AFTER INSERT ON Predictions
FOR EACH ROW
BEGIN
    DECLARE pred_count INT;
    SELECT COUNT(*) INTO pred_count FROM Predictions WHERE user_id = NEW.user_id;
    IF pred_count = 10 THEN
        INSERT IGNORE INTO User_Achievements (user_id, code) VALUES (NEW.user_id, 'locked_in');
    END IF;
END //




CREATE PROCEDURE close_round(IN p_bracket_id INT, IN p_round INT)
BEGIN
    DECLARE max_rounds INT;
    DECLARE e_count INT;

    
    UPDATE Matchups
    SET winner_entrant_id = CASE
        WHEN votes_a >= votes_b THEN entrant_a_id
        ELSE entrant_b_id
    END
    WHERE bracket_id = p_bracket_id AND round = p_round;

   
    UPDATE Predictions p
    JOIN Matchups m ON p.matchup_id = m.matchup_id
    SET p.is_correct = (p.entrant_id = m.winner_entrant_id),
        p.points = CASE WHEN p.entrant_id = m.winner_entrant_id THEN 10 ELSE 0 END
    WHERE m.bracket_id = p_bracket_id AND m.round = p_round;

    
    UPDATE Matchups next_m
    JOIN Matchups prev_m
    ON next_m.bracket_id = prev_m.bracket_id
    AND next_m.round = prev_m.round + 1
    AND next_m.slot = CEIL(prev_m.slot / 2)
    SET next_m.entrant_a_id = prev_m.winner_entrant_id
    WHERE prev_m.bracket_id = p_bracket_id
    AND prev_m.round = p_round
    AND MOD(prev_m.slot, 2) = 1;

    UPDATE Matchups next_m
    JOIN Matchups prev_m
    ON next_m.bracket_id = prev_m.bracket_id
   AND next_m.round = prev_m.round + 1
   AND next_m.slot = CEIL(prev_m.slot / 2)
    SET next_m.entrant_b_id = prev_m.winner_entrant_id
    WHERE prev_m.bracket_id = p_bracket_id
    AND prev_m.round = p_round
    AND MOD(prev_m.slot, 2) = 0;

    
    SELECT entrant_count INTO e_count FROM Brackets WHERE bracket_id = p_bracket_id;
    SET max_rounds = LOG2(e_count);

    IF p_round = max_rounds THEN
        UPDATE Brackets SET status = 'completed' WHERE bracket_id = p_bracket_id;
    ELSE
        UPDATE Brackets SET status = CONCAT('round_', p_round + 1) WHERE bracket_id = p_bracket_id;
    END IF;

END //
DELIMITER ;
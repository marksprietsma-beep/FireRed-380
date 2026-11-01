let remaining = 0;
let active = false;
let turns = 0;
function resume(actions = 10) {
  if (!Number.isInteger(actions) || actions < 1 || actions > 10) throw new Error('Choose 1..10 supervised actions');
  remaining = actions; active = true; turns = actions * 3;
}
function pause() {active = false; remaining = 0; turns = 0;}
function consume() {
  if (!active || remaining <= 0) throw new Error('Operator approval required for next action sequence');
  remaining -= 1;
  if (remaining === 0) active = false;
}
function beginTurn() {
  if (!active || turns <= 0) {pause();throw new Error('Model-turn budget exhausted; operator review required');}
  turns -= 1;
}
function status() {return {active,remaining,modelTurnsRemaining:turns};}
module.exports = {resume,pause,consume,status,beginTurn};

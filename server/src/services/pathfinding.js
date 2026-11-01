// Conservative local BFS: no hosted interpreter or arbitrary generated code.
// Unknown tiles, actors, water, forced movement and boulders are not assumed safe.
function findPath(grid, start, goal) {
  if (!Array.isArray(grid) || !grid.length || !Array.isArray(grid[0])) throw new Error('No collision grid');
  for (const point of [start, goal])
    if (!Number.isInteger(point.x) || !Number.isInteger(point.y) || point.y < 0 || point.y >= grid.length ||
        point.x < 0 || point.x >= grid[point.y].length) throw new Error('Coordinates outside map');
  const queue = [[start.x, start.y, []]], seen = new Set([`${start.x},${start.y}`]);
  for (let i = 0; i < queue.length; i++) {
    const [x,y,path] = queue[i];
    if (x === goal.x && y === goal.y) return path.slice(0,10);
    for (const [dx,dy,key] of [[0,1,'down'],[0,-1,'up'],[-1,0,'left'],[1,0,'right']]) {
      const nx=x+dx, ny=y+dy, id=`${nx},${ny}`;
      if (seen.has(id) || ![1,2].includes(grid[ny]?.[nx])) continue;
      seen.add(id); queue.push([nx,ny,[...path,key]]);
    }
  }
  throw new Error('No known-safe walking path; special terrain requires supervised actions');
}
module.exports = {findPath};

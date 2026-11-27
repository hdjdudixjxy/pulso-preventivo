// Adaptador mínimo con la interfaz de D1 sobre node:sqlite, para la demo local y las pruebas.
import { DatabaseSync } from 'node:sqlite';

export function d1(file=':memory:') {
  const sql=new DatabaseSync(file);
  sql.exec('PRAGMA foreign_keys=ON');
  class Statement {
    constructor(query,params=[]){this.statement=sql.prepare(query);this.params=params;}
    bind(...params){this.params=params;return this;}
    first(){return this.statement.get(...this.params)??null;}
    all(){return {results:this.statement.all(...this.params)};}
    run(){return this.statement.run(...this.params);}
  }
  return {
    sql,
    prepare(query){return new Statement(query);},
    batch(statements){sql.exec('BEGIN');try{const out=statements.map(s=>s.statement.columns().length?s.all():s.run());sql.exec('COMMIT');return out;}catch(e){sql.exec('ROLLBACK');throw e;}}
  };
}

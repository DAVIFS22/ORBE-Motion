// Codificação WAV própria (RIFF/WAVE): PCM 16/24/32 bits ou float32, com dither TPDF determinístico (mulberry32) na quantização.
// O áudio do OfflineAudioContext é Float32 (-1..1); aqui ele é convertido de forma explícita e controlada para o formato de exportação.
// Nada de AudioBuffer "salvo como WAV": o cabeçalho (canais, taxa, bytes por segundo, alinhamento, tamanhos) é escrito e conferido aqui.
import fs from 'node:fs';
import { mulberry32 } from '../engine/rng.js';

export function cabecalhoWav({ canais, taxa, bits, float = false, quadros }) {
  const bytesAmostra = bits / 8, dados = quadros * canais * bytesAmostra;
  const fmtTam = float ? 18 : 16, fact = float ? 12 : 0;                       // float: tag 3 + chunk 'fact' (exigido para formatos não PCM)
  const b = Buffer.alloc(12 + 8 + fmtTam + fact + 8);
  let o = 0;
  const s4 = (t) => { b.write(t, o, 'ascii'); o += 4; }, u32 = (v) => { b.writeUInt32LE(v >>> 0, o); o += 4; }, u16 = (v) => { b.writeUInt16LE(v, o); o += 2; };
  s4('RIFF'); u32(b.length - 8 + dados); s4('WAVE');
  s4('fmt '); u32(fmtTam); u16(float ? 3 : 1); u16(canais); u32(taxa); u32(taxa * canais * bytesAmostra); u16(canais * bytesAmostra); u16(bits); if (float) u16(0);
  if (float) { s4('fact'); u32(4); u32(quadros); }
  s4('data'); u32(dados);
  return b;
}

// Escritor em fluxo: `escrever(Float32Array intercalado)` quantiza (com dither) e grava; `fechar()` confere o total de bytes.
export function criarEscritorWav(caminho, { canais = 2, taxa = 48000, bits = 24, float = false, quadros, dither = true, semente = 7 }) {
  if (float && bits !== 32) throw new Error('float exige 32 bits');
  const fd = fs.openSync(caminho, 'w');
  const cab = cabecalhoWav({ canais, taxa, bits, float, quadros });
  fs.writeSync(fd, cab);
  const rnd = mulberry32(semente);
  let gravados = 0;
  const esperado = quadros * canais * (bits / 8);
  return {
    escrever(x) {
      let buf;
      if (float) buf = Buffer.from(x.buffer, x.byteOffset, x.byteLength);
      else if (bits === 24) {
        buf = Buffer.alloc(x.length * 3);
        const max = 8388607;
        for (let i = 0; i < x.length; i++) {
          const d = dither ? (rnd() - rnd()) : 0;                                   // TPDF: ±1 LSB, sem correlação com o sinal
          let v = Math.round(Math.max(-1, Math.min(1, x[i])) * max + d);
          v = v > max ? max : v < -max - 1 ? -max - 1 : v;
          buf[3 * i] = v & 0xff; buf[3 * i + 1] = (v >> 8) & 0xff; buf[3 * i + 2] = (v >> 16) & 0xff;
        }
      } else if (bits === 16) {
        buf = Buffer.alloc(x.length * 2);
        for (let i = 0; i < x.length; i++) { const d = dither ? (rnd() - rnd()) : 0; buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(Math.max(-1, Math.min(1, x[i])) * 32767 + d))), 2 * i); }
      } else throw new Error('formato não suportado: ' + bits);
      fs.writeSync(fd, buf); gravados += buf.length;
    },
    fechar() { fs.closeSync(fd); if (gravados !== esperado) throw new Error(`WAV incompleto: ${gravados} de ${esperado} bytes`); },
  };
}

export function lerCabecalhoWav(caminho) {
  const fd = fs.openSync(caminho, 'r'); const b = Buffer.alloc(256); fs.readSync(fd, b, 0, 256, 0); const tam = fs.fstatSync(fd).size; fs.closeSync(fd);
  if (b.toString('ascii', 0, 4) !== 'RIFF' || b.toString('ascii', 8, 12) !== 'WAVE') throw new Error('não é WAV');
  let o = 12, fmt = null;
  while (o + 8 <= b.length) {
    const id = b.toString('ascii', o, o + 4), n = b.readUInt32LE(o + 4);
    if (id === 'fmt ') fmt = { tag: b.readUInt16LE(o + 8), canais: b.readUInt16LE(o + 10), taxa: b.readUInt32LE(o + 12), byteRate: b.readUInt32LE(o + 16), alinhamento: b.readUInt16LE(o + 20), bits: b.readUInt16LE(o + 22) };
    if (id === 'data') return { ...fmt, offset: o + 8, bytes: n, arquivo: tam, quadros: n / (fmt.canais * fmt.bits / 8), duracao: n / fmt.byteRate };
    o += 8 + n + (n & 1);
  }
  throw new Error('chunk data não encontrado');
}

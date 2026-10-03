"""System.Random (.NET Framework / Mono) の Python 移植。

Elin (Unity / Mono) の ``Rand`` は ``System.Random`` をそのまま使っているため、
同じシードを与えれば同じ乱数列になる。Knuth の減算法による実装。
"""

from __future__ import annotations

import time

_MBIG = 2147483647  # int.MaxValue
_MSEED = 161803398
_INT_MIN = -2147483648


def to_int32(x: int) -> int:
    """C# の int 演算と同じく 32bit 符号付きに丸める(オーバーフローを再現)。"""
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


class NetRandom:
    """``System.Random`` 互換の乱数生成器。"""

    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            # 引数なし new Random() は Environment.TickCount を使う
            seed = to_int32(int(time.monotonic() * 1000))
        seed = to_int32(seed)
        subtraction = _MBIG if seed == _INT_MIN else abs(seed)
        sa = [0] * 56
        mj = to_int32(_MSEED - subtraction)
        sa[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            sa[ii] = mk
            mk = to_int32(mj - mk)
            if mk < 0:
                mk += _MBIG
            mj = sa[ii]
        for _ in range(1, 5):
            for i in range(1, 56):
                sa[i] = to_int32(sa[i] - sa[1 + (i + 30) % 55])
                if sa[i] < 0:
                    sa[i] = to_int32(sa[i] + _MBIG)
        self._sa = sa
        self._inext = 0
        self._inextp = 21

    def _internal_sample(self) -> int:
        inext = self._inext + 1
        if inext >= 56:
            inext = 1
        inextp = self._inextp + 1
        if inextp >= 56:
            inextp = 1
        # C# の int 演算と同じくすべて 32bit でラップさせる
        ret = to_int32(self._sa[inext] - self._sa[inextp])
        if ret == _MBIG:
            ret -= 1
        if ret < 0:
            ret = to_int32(ret + _MBIG)
        self._sa[inext] = ret
        self._inext = inext
        self._inextp = inextp
        return ret

    def sample(self) -> float:
        return self._internal_sample() * (1.0 / _MBIG)

    def next_double(self) -> float:
        """``Random.NextDouble()``"""
        return self.sample()

    def next(self, max_value: int) -> int:
        """``Random.Next(maxValue)`` : 0 <= x < max_value"""
        if max_value < 0:
            raise ValueError("max_value must be >= 0")
        return int(self.sample() * max_value)

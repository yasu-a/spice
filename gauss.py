import numpy as np


def solve(A, c):
    M = np.concatenate([A, c], axis=1)
    # インデックスベクトル
    idx = np.arange(len(A))
    # Aと同じshapeを持つ対角ベクトルマスク
    I = np.eye(*A.shape, dtype=bool)

    # print('*** MATRIX M')
    # print(M)
    # print()

    repl = []

    # 前進消去
    for i in idx:
        # print(f'FORWARD ON ROW {i}')
        # print(M)
        # print()

        # 対角線を除く下側三角行列が0なら早期終了
        if np.all(np.tril(M[:, :-1])[~I] == 0):
            break

        # 入れ替え
        if M[i, i] == 0:
            j = idx[(M[:, i] != 0) & (idx > i)][0]
            M[i, :], M[j, :] = M[j, :], M[i, :]
            repl.append([i, j])

        # 全身消去のための行基本変形
        #  i行目をi列i行目で除したベクトルvを
        #  (i < j)なるj行目に対してのみ：
        #    j行目からvを-(i列j行目)倍して足す
        M -= M[i] / M[i, i] \
             * np.where(idx <= i, 0, M[:, i])[:, None]

    # print('*** FORWARD RESULT')
    # print(M)
    # print()

    # 後退消去

    # 解を保持するベクトル
    # 移項を内積で処理するので0で初期化しておく
    x = np.zeros(len(A))
    for i in idx[::-1]:
        # print(f'BACKWARD ON ROW {i}')
        # print(f'SOLVE ROW {i} FOR x{i}')
        # print(f'{M[i, i]:10.6f} ', end='')
        # print(f'x{i} = {M[i, -1]:10.6f} - \\')
        # print(f'    ({x} dot \\')
        # print(f'     {M[i, :-1]})')

        # 今まで求めた解を使って今求める項以外を計算し
        # 定数側へ移項，求解
        x[i] = (M[i, -1] - np.dot(x, M[i, :-1])) / M[i, i]

        # nan ならなんでもいい
        if np.isnan(x[i]):
            x[i] = 1

        # print('PARTIAL SOLUTION', x)
        # print()

    # 入れ替えを戻す
    for i, j in reversed(repl):
        x[i], x[j] = x[j], x[i]

    return x

# Лекция 7. ЗБЧ и ЦПТ — короткий конспект

> Полный конспект с выводами: `07_lln-clt.md`.

Обозначения: $E(X)$ — математическое ожидание, $\mathrm{Var}(X)$ — дисперсия, $\sigma=\sqrt{\mathrm{Var}(X)}$, $q=1-p$, $\Phi(x)$ — функция Лапласа ($\Phi(-x)=-\Phi(x)$; $\Phi(1)\approx0{,}341$, $\Phi(2)\approx0{,}477$, $\Phi(3)\approx0{,}4987$, $\Phi(1{,}96)\approx0{,}475$).

## Неравенства

**Маркова.** Для $X\ge0$ и $a>0$:
$$P(X\ge a)\le\frac{E(X)}{a}.$$

**Чебышёва.** Для любой $X$ с конечной дисперсией и $\varepsilon>0$:
$$P(|X-E(X)|\ge\varepsilon)\le\frac{\mathrm{Var}(X)}{\varepsilon^2},\qquad P(|X-E(X)|<\varepsilon)\ge1-\frac{\mathrm{Var}(X)}{\varepsilon^2}.$$

В сигмах: $P(|X-E(X)|\ge k\sigma)\le 1/k^2$ (2σ — не больше 25%, 3σ — не больше 11%).

## Среднее $n$ независимых наблюдений

$X_1,\dots,X_n$ независимы, $E(X_i)=a$, $\mathrm{Var}(X_i)=\sigma^2$, $\bar X=\frac1n(X_1+\ldots+X_n)$:
$$E(\bar X)=a,\qquad \mathrm{Var}(\bar X)=\frac{\sigma^2}{n},\qquad \sigma(\bar X)=\frac{\sigma}{\sqrt n}\ \text{— стандартная ошибка}.$$

Для суммы $S_n=X_1+\ldots+X_n$: $E(S_n)=na$, $\mathrm{Var}(S_n)=n\sigma^2$.

## Закон больших чисел

**Теорема Чебышёва.** Если наблюдения независимы и дисперсия конечна, то для любого $\varepsilon>0$
$$P(|\bar X-a|\ge\varepsilon)\le\frac{\sigma^2}{n\varepsilon^2}\xrightarrow[n\to\infty]{}0.$$

**Теорема Бернулли.** $m$ — число успехов в $n$ независимых опытах с вероятностью успеха $p$:
$$E\left(\frac mn\right)=p,\qquad \mathrm{Var}\left(\frac mn\right)=\frac{pq}{n},\qquad P\left(\left|\frac mn-p\right|\ge\varepsilon\right)\le\frac{pq}{n\varepsilon^2}\le\frac{1}{4n\varepsilon^2}.$$

ЗБЧ — это разбавление, а не компенсация: прошлые исходы не «отыгрываются». Не работает без конечной дисперсии (закон Коши) и при сильной зависимости наблюдений.

## Центральная предельная теорема

Среднее в единицах стандартной ошибки: $Z_n=\dfrac{\bar X-a}{\sigma/\sqrt n}$, $E(Z_n)=0$, $\mathrm{Var}(Z_n)=1$.

**ЦПТ.** Если наблюдения независимы, одинаково распределены и $\sigma$ конечна, то
$$P(z_1<Z_n<z_2)\xrightarrow[n\to\infty]{}\Phi(z_2)-\Phi(z_1).$$

На практике: $\bar X\approx N\left(a,\ \dfrac{\sigma^2}{n}\right)$, $S_n\approx N(na,\ n\sigma^2)$,
$$P(|\bar X-a|<\delta)\approx2\Phi\left(\frac{\delta\sqrt n}{\sigma}\right),\qquad P(\alpha<S_n<\beta)\approx\Phi\left(\frac{\beta-na}{\sigma\sqrt n}\right)-\Phi\left(\frac{\alpha-na}{\sigma\sqrt n}\right).$$

Правило 68–95–99,7: среднее лежит в $a\pm\sigma/\sqrt n$ в 68% выборок, в $a\pm2\sigma/\sqrt n$ — в 95%, в $a\pm3\sigma/\sqrt n$ — в 99,7%.

**Муавр — Лаплас** (ЦПТ для числа успехов): $m\approx N(np,\ npq)$,
$$P(k_1\le m\le k_2)\approx\Phi\left(\frac{k_2-np}{\sqrt{npq}}\right)-\Phi\left(\frac{k_1-np}{\sqrt{npq}}\right),\quad\text{если } np\ge10,\ nq\ge10.$$

## Запомнить

* Чебышёв — гарантия для любого закона, но грубая. ЦПТ — точное приближение при большом $n$.
* Нормальным становится распределение среднего, а не сами данные.
* Сумма многих мелких независимых добавок — колокол; произведение многих множителей — длинный хвост (логнормальный закон).
* Чтобы стать вдвое точнее, нужно вчетверо больше данных.

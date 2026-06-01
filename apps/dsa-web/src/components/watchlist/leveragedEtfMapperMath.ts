export type LeveragedEtfEstimateInput = {
  leverage: number;
  underlyingReference: number;
  etfReference: number;
  underlyingTarget: number;
};

export type ImpliedUnderlyingInput = {
  leverage: number;
  underlyingReference: number;
  etfReference: number;
  etfTarget: number;
};

export function calculateLeveragedEtfEstimate({
  leverage,
  underlyingReference,
  etfReference,
  underlyingTarget,
}: LeveragedEtfEstimateInput): number {
  return etfReference * (1 + leverage * (underlyingTarget / underlyingReference - 1));
}

export function calculateImpliedUnderlying({
  leverage,
  underlyingReference,
  etfReference,
  etfTarget,
}: ImpliedUnderlyingInput): number {
  return underlyingReference * (1 + (etfTarget / etfReference - 1) / leverage);
}

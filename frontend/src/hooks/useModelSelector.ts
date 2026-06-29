import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchModelsWithCanonical,
  fetchRecommendedModels,
  fetchSettings,
} from "../api/client";
import type { ModelEntry } from "../types";

export function useModelSelector(settingsChanged: number, onSelectionChange: (model: string, provider: string) => void) {
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const fetchedProvider = useRef("");
  const savedModelRef = useRef("");
  const onSelectionChangeRef = useRef(onSelectionChange);
  onSelectionChangeRef.current = onSelectionChange;

  useEffect(() => {
    fetchSettings()
      .then((s) => {
        setProvider(s.llm_provider);
        savedModelRef.current = s.llm_model || "";
      })
      .catch(() => {
        setProvider("");
        setModel("");
        setModels([]);
      });
  }, [settingsChanged]);

  useEffect(() => {
    if (!provider) {
      setModels([]);
      setModel("");
      fetchedProvider.current = "";
      return;
    }

    setModel("");
    setLoadingModels(true);
    fetchedProvider.current = provider;

    const canonicalize = (ids: string[]): ModelEntry[] =>
      ids.map((id) => ({
        provider_specific_id: id,
        canonical_slug: null,
        display_name: null,
        family: null,
      }));

    fetchRecommendedModels(provider)
      .then((res) => {
        if (fetchedProvider.current !== provider) return;
        if (res.models.length === 0) {
          setModels([]);
          onSelectionChangeRef.current("", provider);
          return;
        }
        return fetchModelsWithCanonical(provider).then((withCanon) => {
          if (fetchedProvider.current !== provider) return;
          const map = new Map(
            withCanon.models.map((m) => [m.provider_specific_id, m]),
          );
          const entries: ModelEntry[] = res.models.map(
            (id) => map.get(id) ?? canonicalize([id])[0],
          );
          setModels(entries);
          const savedModel = savedModelRef.current;
          const selectedModel =
            savedModel && entries.some((e) => e.provider_specific_id === savedModel)
              ? savedModel
              : entries[0]?.provider_specific_id ?? "";
          setModel(selectedModel);
          onSelectionChangeRef.current(selectedModel, provider);
        });
      })
      .catch(() => {
        if (fetchedProvider.current !== provider) return;
        setModels([]);
        setModel("");
        onSelectionChangeRef.current("", provider);
      })
      .finally(() => {
        if (fetchedProvider.current === provider) {
          setLoadingModels(false);
        }
      });
  }, [provider]);

  const formatModelLabel = useCallback((entry: ModelEntry): string => {
    return entry.display_name || entry.provider_specific_id;
  }, []);

  return {
    provider,
    setProvider,
    model,
    setModel,
    models,
    loadingModels,
    formatModelLabel,
  };
}

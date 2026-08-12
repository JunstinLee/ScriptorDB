import { createContext, useContext } from "react";

export const TABLE_PAGE_SIZE = 20;

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
  paginated: boolean;
}

export const PaginationContext = createContext<PaginationState>({
  page: 0,
  pageSize: TABLE_PAGE_SIZE,
  total: 0,
  paginated: false,
});

export function useTablePagination(): PaginationState {
  return useContext(PaginationContext);
}

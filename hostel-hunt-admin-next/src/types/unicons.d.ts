declare module '@iconscout/react-unicons' {
  import * as React from 'react';
  
  export interface UilIconProps extends React.SVGProps<SVGElement> {
    size?: string | number;
    color?: string;
  }
  
  export type UilIcon = React.FC<UilIconProps>;
  
  export const UilGrids: UilIcon;
  export const UilUsersAlt: UilIcon;
  export const UilCalendarAlt: UilIcon;
  export const UilMoneyBill: UilIcon;
  export const UilBuilding: UilIcon;
  export const UilEdit: UilIcon;
  export const UilBedDouble: UilIcon;
  export const UilSignout: UilIcon;
  export const UilSun: UilIcon;
  export const UilMoon: UilIcon;
  export const UilBars: UilIcon;
  export const UilBell: UilIcon;
}

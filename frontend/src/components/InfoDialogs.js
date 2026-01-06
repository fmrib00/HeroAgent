import React from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography, List, ListItem
} from "@mui/material";

function InfoDialogs({ 
  missingHallDialogOpen, 
  setMissingHallDialogOpen, 
  missingHallAccounts,
  missingAccountsDialogOpen, 
  setMissingAccountsDialogOpen, 
  missingAccounts 
}) {
  return (
    <>
      <Dialog open={missingHallDialogOpen} onClose={() => setMissingHallDialogOpen(false)}>
        <DialogTitle>账号缺少幻境设置</DialogTitle>
        <DialogContent>
          <Typography>以下账号缺少幻境设置，请先设置后再进行挑战：</Typography>
          <List>
            {missingHallAccounts.map(name => (
              <ListItem key={name}>{name}</ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMissingHallDialogOpen(false)}>确定</Button>
        </DialogActions>
      </Dialog>
      
      <Dialog open={missingAccountsDialogOpen} onClose={() => setMissingAccountsDialogOpen(false)}>
        <DialogTitle>账号信息获取失败</DialogTitle>
        <DialogContent>
          <Typography>以下账号无法获取信息，可能已被删除或不存在：</Typography>
          <List>
            {missingAccounts.map(name => (
              <ListItem key={name}>{name}</ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMissingAccountsDialogOpen(false)}>确定</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

export default InfoDialogs; 